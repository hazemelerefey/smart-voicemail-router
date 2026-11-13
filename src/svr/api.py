"""SVR Phase 1 API (contracts section 6).

FastAPI app. All endpoints work on the mock pipeline; no model is loaded
and no real data is involved.

Endpoints:
  POST   /api/voicemails        submit an upload, 202 + ticket id + status
  GET    /api/tickets/{id}      ticket fields, evidence, timing, route reason
  GET    /api/agents            seeded demo agents only
  PATCH  /api/tickets/{id}      manual status / reassignment, with audit event
  GET    /api/latency           p95 latency report with hardware (section 7)
  WS     /ws/queue              queue snapshot on connect, plus a live
                                ticket_update broadcast when a run completes
  GET    /                      plain HTML demo page (upload, run, ticket)
"""

from __future__ import annotations

import threading
import uuid

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, field_validator

from . import agents as agents_module
from .latency import summarize_latency
from .pipeline import PipelineResult, run_pipeline
from .schemas import (
    LABEL_VERSION,
    SCHEMA_VERSION,
    Agent,
    AssignmentStatus,
    TicketDetail,
    TicketStatus,
    utcnow_iso,
)
from .stages.intake import MAX_BYTES, AudioMeta, validate_and_measure
from .stages.ticket import build_review_ticket
from .store import STORE

# Uploads are read in 1 MiB chunks (issue #5): the size limit is enforced
# during ingest, never after the whole file is in memory.
_CHUNK_SIZE = 1024 * 1024


async def _read_upload_limited(file: UploadFile, limit_bytes: int = MAX_BYTES) -> bytes:
    """Read an upload in chunks, aborting past the size limit. Never holds
    more than one chunk plus the limit in memory, and never calls intake
    validation on an oversize file: the 25 MB rejection happens here."""
    data = bytearray()
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            return bytes(data)
        if len(data) + len(chunk) > limit_bytes:
            raise ValueError(
                f"file exceeds the {limit_bytes // (1024 * 1024)} MB limit"
            )
        data += chunk

app = FastAPI(title="SVR Phase 1 API (mock pipeline)", version="1.0.0-mock")


# ---------------------------------------------------------------- WebSocket
class QueueHub:
    """Queue hub: sends the queue snapshot on connect, then broadcasts a
    ticket_update to every connected client when a run completes. A push
    broadcaster refinement (dedicated broadcaster task, reconnect handling)
    stays a Phase 3 item.

    The connection list is guarded by a lock, and dead connections are
    removed after a failed send, so a dropped client never stays in the
    list (issue #9).
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._connections.append(websocket)
        await websocket.send_json(
            {"type": "queue_snapshot", "tickets": [t.model_dump() for t in STORE.list_tickets()]}
        )

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)


HUB = QueueHub()


# ------------------------------------------------------------------ helpers
async def _run_and_store(ticket_id: str, voicemail_id: str, meta: AudioMeta) -> None:
    """Run the mock pipeline on upload metadata only (no audio bytes are
    carried here), store the finished ticket, then broadcast the completed
    ticket to every connected /ws/queue client.

    A pipeline exception outside the per-stage fail path must never leave
    the ticket stuck at ``processing``: the run is stored as a
    ``needs_review`` ticket instead, and the failure is still broadcast.
    """
    try:
        result = run_pipeline(meta, voicemail_id, ticket_id=ticket_id)
        ticket = STORE.complete(result)
    except Exception as exc:
        review = build_review_ticket(
            ticket_id=ticket_id,
            voicemail_id=voicemail_id,
            route_reason=f"Pipeline failed unexpectedly: {exc}",
            stage_status={"pipeline": "failed"},
            stage_timing_ms={},
            processing_ms=0.0,
        )
        try:
            ticket = STORE.complete(PipelineResult(review, None, None, None, None))
        except Exception:
            # The store itself failed: still broadcast the review ticket
            # below so the client is never left waiting on "processing".
            ticket = review
    await HUB.broadcast(
        {
            "type": "ticket_update",
            "ticket_id": ticket.id,
            "ticket": ticket.model_dump(mode="json"),
            "tickets": [t.model_dump(mode="json") for t in STORE.list_tickets()],
        }
    )


class SubmitResponse(BaseModel):
    ticket_id: str
    voicemail_id: str
    status: str
    message: str


# Known audit actors: the six team members plus the system actors the
# store itself uses ("system" for pipeline events, "demo-user" for the
# demo). Any other actor value is rejected on PATCH (issue #9).
KNOWN_ACTORS = frozenset(
    {"system", "demo-user", "hazem", "arafa", "sira", "lama", "aya", "ibthal"}
)


class PatchTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_status: TicketStatus | None = None
    assignment_status: AssignmentStatus | None = None
    assigned_agent_id: str | None = None
    actor: str = "demo-user"

    @field_validator("actor")
    @classmethod
    def _validate_actor(cls, value: str) -> str:
        # The audit actor is validated against a known set (issue #9):
        # any caller stamping events as someone else is rejected.
        if value not in KNOWN_ACTORS:
            raise ValueError(
                f"unknown audit actor: {value!r}; known actors: "
                + ", ".join(sorted(KNOWN_ACTORS))
            )
        return value


# ----------------------------------------------------------------- endpoints
@app.post("/api/voicemails", status_code=202, response_model=SubmitResponse)
async def submit_voicemail(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
) -> SubmitResponse:
    """Submit an upload. 202 Accepted with ticket id and status; the ticket
    is visible as processing within 2 seconds, before analysis
    begins (contracts section 5). Analysis runs in the background.
    Invalid format, size or duration is rejected here with a clear 400
    error (contracts section 5); valid input is never rejected. The size
    limit is enforced while the upload streams in (1 MiB chunks), so an
    oversize file is rejected before it is ever fully read. Duration is
    enforced for WAV only: MP3/M4A duration is not measurable with the
    stdlib, and Sira's audio pipeline measures it in Phase 2. Uploaded
    bytes are read only to check size and format, then discarded: the
    background task carries the measured metadata only, and Phase 1
    persists no audio."""
    try:
        data = await _read_upload_limited(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = file.filename or "upload.wav"
    voicemail_id = f"voicemail-{uuid.uuid4().hex[:12]}"
    ticket_id = f"ticket-{uuid.uuid4().hex[:12]}"
    try:
        meta: AudioMeta = validate_and_measure(data, filename, voicemail_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        # Bytes are discarded after this check. Phase 1 persists no audio.
        del data
    STORE.create_placeholder(ticket_id, voicemail_id)
    background_tasks.add_task(_run_and_store, ticket_id, voicemail_id, meta)
    return SubmitResponse(
        ticket_id=ticket_id,
        voicemail_id=voicemail_id,
        status="processing",
        message="Accepted. Poll GET /api/tickets/{ticket_id} for the result.",
    )


@app.get("/api/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: str) -> TicketDetail:
    detail = STORE.get_detail(ticket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return detail


@app.get("/api/agents", response_model=list[Agent])
async def get_agents() -> list[Agent]:
    """Seeded demo agents only. No real people."""
    return agents_module.list_agents()


@app.patch("/api/tickets/{ticket_id}", response_model=TicketDetail)
async def patch_ticket(ticket_id: str, patch: PatchTicket) -> TicketDetail:
    # Ticket existence first: a PATCH on a missing ticket is a 404 for the
    # ticket, even when the agent id is also invalid (issue #4).
    if STORE.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if patch.assigned_agent_id is not None and agents_module.get_agent(patch.assigned_agent_id) is None:
        raise HTTPException(status_code=404, detail="agent not found")
    assignment_status = patch.assignment_status
    if (
        assignment_status == AssignmentStatus.UNASSIGNED
        and patch.assigned_agent_id is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="cannot set assigned_agent_id while assignment_status is unassigned",
        )
    if patch.assigned_agent_id is not None and assignment_status is None:
        # Naming an agent assigns the ticket.
        assignment_status = AssignmentStatus.ASSIGNED
    if assignment_status == AssignmentStatus.ASSIGNED and patch.assigned_agent_id is None:
        # "assigned" with no agent id is rejected unless the ticket already
        # has an assigned agent.
        detail = STORE.get_detail(ticket_id)
        current_agent = (
            detail.triage_decision.assigned_agent_id
            if detail is not None and detail.triage_decision is not None
            else None
        )
        if current_agent is None:
            raise HTTPException(
                status_code=400,
                detail="assignment_status assigned requires an assigned_agent_id",
            )
    try:
        updated = STORE.update(
            ticket_id,
            ticket_status=patch.ticket_status.value if patch.ticket_status else None,
            assignment_status=assignment_status.value if assignment_status else None,
            assigned_agent_id=patch.assigned_agent_id,
            actor=patch.actor,
        )
    except ValueError as exc:
        # Invalid assignment or status change (agent at capacity,
        # contradictory fields, invalid transition): a 400, nothing stored.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    detail = STORE.get_detail(ticket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return detail


@app.get("/api/latency")
async def get_latency() -> dict:
    """p95 latency report (contracts section 7), with hardware recorded."""
    processing, stages = STORE.latency_samples()
    return summarize_latency(processing, stages)


@app.websocket("/ws/queue")
async def queue_socket(websocket: WebSocket) -> None:
    """Queue stream: sends the queue snapshot on connect, then a live
    ticket_update broadcast each time a run completes (see _run_and_store).
    A push broadcaster refinement stays a Phase 3 item."""
    await HUB.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        HUB.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
async def demo_page() -> str:
    """Plain HTML demo (upload, run, ticket display). Gradio demo is in
    demo.py; this page needs no extra dependency."""
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SVR Phase 1 Demo (mock)</title>
<style>body{font-family:sans-serif;max-width:720px;margin:2em auto;padding:0 1em}
pre{background:#f4f4f4;padding:1em;overflow:auto}.flag{font-weight:bold}
.cached{color:#b00}.ok{color:#080}</style></head><body>
<h1>Smart Voicemail Router, Phase 1 Demo (MOCK)</h1>
<p>Upload a WAV / MP3 / M4A file (max 25 MB, 60 s). The pipeline is a mock:
fixed fixture transcript and fields, no real model, no real data.</p>
<form id="f"><input type="file" name="file" accept=".wav,.mp3,.m4a" required>
<button type="submit">Run pipeline</button></form>
<p id="status"></p>
<h2>Ticket</h2>
<div id="ticket"><p><i>No run yet.</i></p></div>
<script>
const f=document.getElementById('f'),s=document.getElementById('status'),t=document.getElementById('ticket');
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function flagSpan(value){const n=el('span',String(value));n.className='flag '+(value?'cached':'ok');return n;}
f.addEventListener('submit',async e=>{e.preventDefault();
  s.textContent='Uploading…';t.replaceChildren();
  const r=await fetch('/api/voicemails',{method:'POST',body:new FormData(f)});
  const j=await r.json();
  if(!r.ok){s.textContent='Error: '+(j.detail||r.status);return;}
  s.textContent='Ticket '+j.ticket_id+' ('+j.status+'). Polling…';
  for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,250));
    const g=await fetch('/api/tickets/'+j.ticket_id);const d=await g.json();
    if(d.ticket_status==='completed'||d.ticket_status==='needs_review'){
      s.textContent='Done in '+d.processing_ms+' ms.';
      const p1=el('p');p1.append('cached: ',flagSpan(d.cached),'  needs_human_review: ',flagSpan(d.needs_human_review));
      const p2=el('p');p2.append(el('b','Route reason: '),document.createTextNode(d.route_reason));
      const p3=el('p');p3.append(el('b','Stage timings (ms): '),document.createTextNode(JSON.stringify(d.stage_timing_ms)));
      t.replaceChildren(p1,p2,p3,el('pre',JSON.stringify(d,null,2)));
      return;}}
  s.textContent='Still processing after 10 s.';});
</script></body></html>"""


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "schema_version": SCHEMA_VERSION, "label_version": LABEL_VERSION, "mode": "mock", "time": utcnow_iso()}
