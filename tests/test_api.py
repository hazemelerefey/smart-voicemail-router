"""API tests: submit, poll, agents, patch + audit, latency, websocket."""

import io
import time
import wave

from fastapi.testclient import TestClient

from svr.api import app
from svr.store import STORE

client = TestClient(app)


def make_wav_bytes(duration_s: float = 1.0, rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * channels * int(rate * duration_s))
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


def test_patch_reassignment_persists_on_triage_decision():
    """PATCH with a valid agent id changes the stored triage decision, so
    GET shows the new agent as structured data, not free text."""
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    ticket_id = resp.json()["ticket_id"]
    poll_ticket(ticket_id)
    assert (
        client.get(f"/api/tickets/{ticket_id}")
        .json()["triage_decision"]["assigned_agent_id"]
        == "agent-demo-network"
    )
    patched = client.patch(
        f"/api/tickets/{ticket_id}",
        json={"assigned_agent_id": "agent-demo-billing"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["assignment_status"] == "assigned"
    assert (
        patched.json()["triage_decision"]["assigned_agent_id"]
        == "agent-demo-billing"
    )
    detail = client.get(f"/api/tickets/{ticket_id}").json()
    assert detail["triage_decision"]["assigned_agent_id"] == "agent-demo-billing"
    assert detail["triage_decision"]["assignment_status"] == "assigned"


def test_patch_unknown_ticket_404_even_with_unknown_agent():
    """Ticket existence is checked first: a PATCH on a missing ticket is a
    404 for the ticket, even when the agent id is also invalid."""
    resp = client.patch(
        "/api/tickets/ticket-does-not-exist",
        json={"assigned_agent_id": "agent-does-not-exist"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "ticket not found"


def test_patch_contradictory_assignment_400():
    """Contradictory assignment fields are rejected: an agent id with
    unassigned, and assigned with no agent id on a ticket that has none."""
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    ticket_id = resp.json()["ticket_id"]
    poll_ticket(ticket_id)
    assert (
        client.patch(
            f"/api/tickets/{ticket_id}",
            json={
                "assignment_status": "unassigned",
                "assigned_agent_id": "agent-demo-network",
            },
        ).status_code
        == 400
    )
    # Unassign first, then "assigned" with no agent id must fail.
    assert (
        client.patch(
            f"/api/tickets/{ticket_id}", json={"assignment_status": "unassigned"}
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/tickets/{ticket_id}")
        .json()["triage_decision"]["assigned_agent_id"]
        is None
    )
    assert (
        client.patch(
            f"/api/tickets/{ticket_id}", json={"assignment_status": "assigned"}
        ).status_code
        == 400
    )


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


def test_wav_ticket_evidence_reports_measured_values():
    """A live WAV ticket shows audio_path_local null (Phase 1 persists no
    audio) and duration/sample rate/channels equal to the real WAV header."""
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.wav", make_wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 202, resp.text
    ticket = poll_ticket(resp.json()["ticket_id"])
    evidence = ticket["audio_evidence"]
    assert evidence["audio_path_local"] is None
    assert evidence["duration_s"] == 1.0
    assert evidence["sample_rate_hz"] == 16000
    assert evidence["channels"] == 1
    assert evidence["format"] == "wav"


def test_stereo_wav_ticket_evidence_reports_header_values():
    """A 44.1 kHz stereo WAV does not get evidence claiming 16 kHz mono."""
    resp = client.post(
        "/api/voicemails",
        files={
            "file": (
                "stereo.wav",
                make_wav_bytes(duration_s=1.0, rate=44100, channels=2),
                "audio/wav",
            )
        },
    )
    assert resp.status_code == 202, resp.text
    ticket = poll_ticket(resp.json()["ticket_id"])
    evidence = ticket["audio_evidence"]
    assert evidence["audio_path_local"] is None
    assert evidence["duration_s"] == 1.0
    assert evidence["sample_rate_hz"] == 44100
    assert evidence["channels"] == 2


def test_mp3_ticket_evidence_leaves_unmeasured_fields_null():
    """A live MP3 ticket shows duration/sample rate/channels null, never
    0.0 or a hardcoded value, and no uploads/ path."""
    resp = client.post(
        "/api/voicemails",
        files={"file": ("test.mp3", b"ID3" + b"\x00" * 100, "audio/mpeg")},
    )
    assert resp.status_code == 202, resp.text
    ticket = poll_ticket(resp.json()["ticket_id"])
    assert ticket["ticket_status"] == "completed"
    evidence = ticket["audio_evidence"]
    assert evidence["audio_path_local"] is None
    assert evidence["duration_s"] is None
    assert evidence["sample_rate_hz"] is None
    assert evidence["channels"] is None
    assert evidence["format"] == "mp3"


def test_background_task_exception_still_broadcasts_needs_review(monkeypatch):
    """A pipeline exception outside the per-stage fail path still stores a
    needs_review ticket and still broadcasts a ticket_update: the client is
    never left on "Still processing"."""
    import threading

    import svr.api as api_module

    monkeypatch.setattr(
        api_module,
        "run_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("forced pipeline failure for the test")
        ),
    )
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
        assert msg["ticket"]["ticket_status"] == "needs_review"
        assert "pipeline failed" in msg["ticket"]["route_reason"].lower()
    detail = client.get(f"/api/tickets/{ticket_id}").json()
    assert detail["ticket_status"] == "needs_review"
    assert detail["stage_status"].get("pipeline") == "failed"
