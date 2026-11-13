"""API tests: submit, poll, agents, patch + audit, latency, websocket."""

import io
import time
import wave

from fastapi.testclient import TestClient

from svr.api import app
from svr.store import STORE

client = TestClient(app)


def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * duration_s))
    return buf.getvalue()


def poll_ticket(ticket_id: str, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/tickets/{ticket_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        if data["ticket_status"] in ("completed", "needs_review"):
            return data
        time.sleep(0.05)
    raise AssertionError(f"ticket {ticket_id} did not finish within {timeout_s}s")


def test_submit_wav_returns_202_and_ticket_completes():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "processing"
    ticket = poll_ticket(body["ticket_id"])
    assert ticket["ticket_status"] == "completed"
    assert ticket["complaint_category"] == "network_and_connectivity"
    assert ticket["complaint_urgency"] == "medium"
    assert ticket["customer_state_text"] == "frustrated"
    assert ticket["churn_risk"] == "not_at_risk"
    assert ticket["customer_state_final"] is None
    assert ticket["needs_human_review"] is False
    assert ticket["cached"] is False
    assert ticket["stage_status"]["voice_evidence"] == "skipped"
    assert ticket["processing_ms"] > 0
    assert ticket["processing_ms"] < 10_000
    assert ticket["transcript"] == "[fixture transcript]"
    assert "Assigned because" in ticket["route_reason"]


def test_ticket_visible_within_2s_of_submit():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 202
    ticket_id = resp.json()["ticket_id"]
    start = time.time()
    got = client.get(f"/api/tickets/{ticket_id}")
    assert time.time() - start < 2.0
    assert got.status_code == 200
    assert got.json()["ticket_status"] in ("processing", "completed", "needs_review")


def test_submit_rejects_wrong_format():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert "WAV, MP3, M4A" in resp.json()["detail"]


def test_submit_rejects_oversize_file():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("big.wav", b"\x00" * (25 * 1024 * 1024 + 1), "audio/wav")},
    )
    assert resp.status_code == 400
    assert "25 MB" in resp.json()["detail"]


def test_submit_rejects_wav_over_60s():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("long.wav", make_wav_bytes(duration_s=61.0), "audio/wav")},
    )
    assert resp.status_code == 400
    assert "60 second" in resp.json()["detail"]


def test_get_unknown_ticket_404():
    assert client.get("/api/tickets/ticket-does-not-exist").status_code == 404


def test_agents_are_seeded_demo_only():
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 3
    assert all("Demo Agent" in a["name"] for a in agents)
    assert agents[0]["skills"] == ["network_and_connectivity", "no_reply_or_long_wait"]
    assert all(a["on_shift"] for a in agents)


def test_patch_ticket_writes_audit_event():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    ticket_id = resp.json()["ticket_id"]
    poll_ticket(ticket_id)
    patched = client.patch(
        f"/api/tickets/{ticket_id}",
        json={"assignment_status": "unassigned", "actor": "demo-user"},
    )
    assert patched.status_code == 200
    assert patched.json()["assignment_status"] == "unassigned"
    detail = client.get(f"/api/tickets/{ticket_id}").json()
    events = [e["event"] for e in detail["events"]]
    assert "submitted" in events
    assert "completed" in events
    assert "manual_update" in events
    assert detail["triage_decision"]["route_reason"]


def test_patch_unknown_agent_404():
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    ticket_id = resp.json()["ticket_id"]
    poll_ticket(ticket_id)
    assert (
        client.patch(
            f"/api/tickets/{ticket_id}",
            json={"assigned_agent_id": "agent-does-not-exist"},
        ).status_code
        == 404
    )


def test_latency_endpoint_reports_p95_and_hardware():
    resp = client.get("/api/latency")
    assert resp.status_code == 200
    data = resp.json()
    assert "p95_processing_ms" in data
    assert "hardware" in data
    assert data["target_ms"] == 10_000.0
    assert data["hardware"]["cpu_count"] is not None


def test_placeholder_ticket_needs_review_and_has_no_labels():
    """A queued/processing ticket carries no labels and needs_human_review
    True until its run finishes, so it can never be mistaken for an answer."""
    from svr.store import TicketStore

    store = TicketStore()
    ticket = store.create_placeholder("ticket-test-001", "voicemail-test-001")
    assert ticket.ticket_status.value == "processing"
    assert ticket.needs_human_review is True
    assert ticket.complaint_category is None
    assert ticket.complaint_urgency is None
    assert ticket.customer_state_text is None
    assert ticket.churn_risk is None
    assert ticket.voice_state_candidate is None
    assert ticket.transcript == ""
    assert ticket.summary == ""


def test_websocket_queue_snapshot():
    with client.websocket_connect("/ws/queue") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "queue_snapshot"
        assert isinstance(msg["tickets"], list)


def test_websocket_receives_completed_ticket_update():
    """A connected /ws/queue client gets a ticket_update when a POSTed run
    completes, not just the snapshot on connect."""
    import threading

    received: dict = {}

    def _recv(ws):
        try:
            received["msg"] = ws.receive_json()
        except Exception as exc:  # noqa: BLE001 - record, do not raise in thread
            received["error"] = exc

    with client.websocket_connect("/ws/queue") as ws:
        assert ws.receive_json()["type"] == "queue_snapshot"
        resp = client.post(
            "/api/voicemails",
            files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
        )
        assert resp.status_code == 202, resp.text
        ticket_id = resp.json()["ticket_id"]
        thread = threading.Thread(target=_recv, args=(ws,), daemon=True)
        thread.start()
        thread.join(timeout=5.0)
        assert not thread.is_alive(), "no websocket update received in 5s"
        assert "error" not in received, received["error"]
        msg = received["msg"]
        assert msg["type"] == "ticket_update"
        assert msg["ticket_id"] == ticket_id
        assert msg["ticket"]["ticket_status"] == "completed"
        assert msg["ticket"]["complaint_category"] == "network_and_connectivity"


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "mock"
    assert resp.json()["label_version"] == "taxonomy-2026-11-11"


def test_demo_markdown_shows_flags_timings_and_reason():
    from svr.demo import format_ticket_markdown
    from svr.pipeline import run_pipeline
    from svr.stages.intake import validate_and_measure

    meta = validate_and_measure(make_wav_bytes(), "test.wav", "voicemail-demo-001")
    result = run_pipeline(meta, "voicemail-demo-001")
    text = format_ticket_markdown(result.ticket)
    assert "Cached:" in text
    assert "Needs human review:" in text
    assert "Route reason:" in text
    assert "Stage timings:" in text
    assert "fusion disabled" in text
