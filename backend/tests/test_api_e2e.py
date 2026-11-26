"""End-to-end API, workflow (WF1-WF4), WebSocket, and security tests for SVR."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from svr_platform.api.main import create_app
from svr_platform.services.classification import MARBERTv2ClassifierService
from svr_platform.services.stt import WhisperSTTService
from svr_platform.services.transcript_gate import TranscriptVerificationGate
from svr_platform.taxonomy import DEFAULT_SKILL_MAPPING, TRAINED_CLASSES_BY_FIELD
from tests.conftest import make_wav_bytes


def _make_probs(field: str, winner: str, top_prob: float) -> dict[str, float]:
    classes = TRAINED_CLASSES_BY_FIELD[field]
    others = [c for c in classes if c != winner]
    rem = (1.0 - top_prob) / len(others)
    probs = {c: round(rem, 6) for c in others}
    probs[winner] = round(1.0 - sum(probs.values()), 6)
    return probs


def _build_prediction(
    category: str = "network_and_connectivity",
    urgency: str = "high",
    state: str = "frustrated",
    churn: str = "not_at_risk",
    confidence: float = 0.88,
) -> dict[str, dict[str, Any]]:
    return {
        "complaint_category": {
            "label": category,
            "probabilities": _make_probs("complaint_category", category, max(confidence, 0.91)),
        },
        "complaint_urgency": {
            "label": urgency,
            "probabilities": _make_probs("complaint_urgency", urgency, confidence),
        },
        "customer_state": {
            "label": state,
            "probabilities": _make_probs("customer_state", state, max(confidence, 0.90)),
        },
        "churn_risk": {
            "label": churn,
            "probabilities": _make_probs("churn_risk", churn, max(confidence, 0.93)),
        },
    }


@pytest.fixture()
def api_env(test_settings, db_manager):
    state = {
        "transcript": "الشبكة عندي في ال 4G ضعيفة جدا ومش عارف اتصل",
        "prediction": _build_prediction(),
    }

    stt = WhisperSTTService(
        transcriber_override=lambda _audio, _fmt: {
            "text": state["transcript"],
            "min_avg_logprob": -0.18,
            "max_no_speech_prob": 0.05,
        }
    )
    gate = TranscriptVerificationGate(
        reviewer_override=lambda ctx: {
            "thinking": "Transcript is clear Egyptian Arabic with 4G telecom term.",
            "suspect_words": [],
            "corrected_text": ctx["current_text"],
            "confidence": 0.94,
            "is_coherent": True,
            "changes": [],
        }
    )
    clf = MARBERTv2ClassifierService(
        models_dir=test_settings.svr_models_dir,
        repo_root=test_settings.repo_root,
        allow_validated_artifact_fallback=False,
        predictor_override=lambda _text_norm: state["prediction"],
    )
    app = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=stt,
        transcript_gate=gate,
        classifier_service=clf,
    )
    return app, test_settings, state


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    csrf_cookie = client.cookies.get("svr_csrf")
    assert csrf_cookie
    assert res.json()["csrf_token"] == csrf_cookie
    return {"X-CSRF-Token": csrf_cookie}


def test_wf1_upload_pipeline_dedup_validation_and_audio_playback(api_env):
    app, cfg, state = api_env
    with TestClient(app) as client:
        headers = _login(client, "supervisor@telecom.local", cfg.svr_bootstrap_password)

        # Invalid format rejected BEFORE creating any ticket
        bad_fmt = client.post(
            "/api/voicemails",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
            headers=headers,
        )
        assert bad_fmt.status_code == 400
        assert "format" in bad_fmt.json()["detail"].lower()

        # Over-duration (> 60s) rejected BEFORE creating any ticket
        long_wav = make_wav_bytes(duration_s=62.0)
        bad_dur = client.post(
            "/api/voicemails",
            files={"file": ("too_long.wav", long_wav, "audio/wav")},
            headers=headers,
        )
        assert bad_dur.status_code == 400
        assert "duration" in bad_dur.json()["detail"].lower()

        assert client.get("/api/tickets").json()["total"] == 0

        # Valid WAV upload returns 202 with status='processing' within < 2s
        wav_bytes = make_wav_bytes(duration_s=2.5)
        t0 = time.perf_counter()
        up_res = client.post(
            "/api/voicemails",
            files={"file": ("subscriber_01.wav", wav_bytes, "audio/wav")},
            headers={**headers, "Idempotency-Key": "req-wf1-001"},
        )
        elapsed = time.perf_counter() - t0
        assert up_res.status_code == 202, up_res.text
        assert elapsed < 2.0
        up_body = up_res.json()
        assert up_body["status"] == "processing"
        assert up_body["deduplicated"] is False
        assert up_body["recommendation_note"] is not None  # < 15s recommendation note, accepted
        ticket_id = up_body["ticket_id"]
        vm_id = up_body["voicemail_id"]

        # Duplicate upload with same Idempotency-Key returns existing ticket (NFR13)
        dup_res = client.post(
            "/api/voicemails",
            files={"file": ("subscriber_01.wav", wav_bytes, "audio/wav")},
            headers={**headers, "Idempotency-Key": "req-wf1-001"},
        )
        assert dup_res.status_code == 200
        assert dup_res.json()["deduplicated"] is True
        assert dup_res.json()["ticket_id"] == ticket_id

        # Ticket detail contains full WF1 outputs, 10-col STT v1, probabilities, S4 provenance, brief, logs
        detail_res = client.get(f"/api/tickets/{ticket_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["status"] == "ready"
        assert detail["complaint_category"] == "network_and_connectivity"
        assert detail["complaint_urgency"] == "high"
        assert detail["customer_state"] == "frustrated"
        assert detail["churn_risk"] == "not_at_risk"
        assert detail["priority_score"] == 4
        assert detail["queue_priority"] == "normal"
        assert detail["assigned_agent_name"] == "Network Care Specialist"
        assert detail["language_mix"] == "english_telecom_terms"
        assert set(detail["stt_v1_json"].keys()) == {
            "file",
            "model",
            "text",
            "text_norm",
            "min_avg_logprob",
            "max_no_speech_prob",
            "needs_review",
            "review_reasons",
            "dup_text_size",
            "error",
        }
        assert all(v == "model" for v in detail["label_sources"].values())
        assert len(detail["summary"]) <= 200
        assert detail["suggested_script"] != ""
        stages = [log["stage"] for log in detail["ai_logs"]]
        assert stages == ["transcribe", "verify_transcript", "classify", "priority", "route", "brief"]
        assert detail["transcript_verification"]["agent_name"] == "VoiceGate Orchestrator"
        assert detail["transcript_verification"]["status"] == "verified"

        # Encrypted audio decrypts and streams cleanly
        audio_res = client.get(f"/api/voicemails/{vm_id}/audio")
        assert audio_res.status_code == 200
        assert audio_res.headers["content-type"].startswith("audio/wav")
        assert audio_res.content == wav_bytes

        # Arabic-normalized search matches unnormalized query 'الشبكة' against text_norm 'الشبكه'
        search_res = client.get("/api/tickets", params={"q": "الشبكة"})
        assert search_res.status_code == 200
        assert search_res.json()["total"] == 1
        assert search_res.json()["items"][0]["id"] == ticket_id


def test_wf2_preview_and_apply_correction_and_wf3_lifecycle(api_env):
    app, cfg, state = api_env
    with TestClient(app) as client:
        headers = _login(client, "supervisor@telecom.local", cfg.svr_bootstrap_password)

        # Create a low-confidence ticket so it enters Human Review Queue (WF3)
        state["prediction"] = _build_prediction(
            category="network_and_connectivity",
            urgency="low",
            state="calm",
            churn="not_at_risk",
            confidence=0.35,
        )
        up = client.post(
            "/api/voicemails",
            files={"file": ("low_conf.wav", make_wav_bytes(1.5), "audio/wav")},
            headers=headers,
        )
        assert up.status_code == 202
        ticket_id = up.json()["ticket_id"]

        review_q = client.get(
            "/api/tickets",
            params={"needs_human_review": "true", "review_reason": "low_confidence"},
        )
        assert review_q.status_code == 200
        assert review_q.json()["total"] == 1
        assert review_q.json()["items"][0]["status"] == "unassigned"

        # WF2 Step 4: preview-correction computes new priority & Billing agent WITHOUT mutating DB
        prev_res = client.post(
            f"/api/tickets/{ticket_id}/preview-correction",
            json={
                "complaint_category": "billing_and_charges",
                "complaint_urgency": "high",
                "customer_state": "mad",
                "churn_risk": "at_risk",
            },
            headers=headers,
        )
        assert prev_res.status_code == 200, prev_res.text
        prev = prev_res.json()
        assert prev["priority_score"] == 6
        assert prev["queue_priority"] == "urgent"
        assert prev["recommended_agent_name"] == "Billing & Bundles Specialist"

        # Confirm DB was NOT mutated by preview
        unchanged = client.get(f"/api/tickets/{ticket_id}").json()
        assert unchanged["complaint_category"] == "network_and_connectivity"
        assert unchanged["priority_score"] == 1
        assert unchanged["status"] == "unassigned"

        # WF2 Step 5: apply correction updates labels, marks human provenance (S4), routes to Billing
        corr_res = client.post(
            f"/api/tickets/{ticket_id}/correct",
            json={
                "complaint_category": "billing_and_charges",
                "complaint_urgency": "high",
                "churn_risk": "at_risk",
                "note": "Supervisor verified billing dispute and cancellation threat",
            },
            headers=headers,
        )
        assert corr_res.status_code == 200, corr_res.text
        corrected = corr_res.json()
        assert corrected["complaint_category"] == "billing_and_charges"
        assert corrected["priority_score"] == 5  # high(3) + at_risk(2) + calm(0)
        assert corrected["queue_priority"] == "high"
        assert corrected["assigned_agent_name"] == "Billing & Bundles Specialist"
        assert corrected["status"] == "ready"
        assert corrected["needs_human_review"] is False
        assert corrected["label_sources"]["complaint_category"] == "human"
        assert corrected["label_sources"]["complaint_urgency"] == "human"
        assert corrected["label_sources"]["churn_risk"] == "human"
        assert corrected["label_sources"]["customer_state"] == "model"  # untouched stays model!

        # Verify audit event captures old_value, new_value, actor, and timestamp
        corr_events = [e for e in corrected["audit_events"] if e["action"] == "corrected"]
        assert len(corr_events) == 1
        assert corr_events[0]["actor"] == "supervisor@telecom.local"
        assert corr_events[0]["old_value"]["complaint_category"] == "network_and_connectivity"
        assert corr_events[0]["new_value"]["complaint_category"] == "billing_and_charges"

        # Verify capacity consumed (1) and released on resolved -> closed
        agents_before = {a["name"]: a for a in client.get("/api/agents").json()}
        assert agents_before["Billing & Bundles Specialist"]["current_load"] == 1

        p1 = client.patch(f"/api/tickets/{ticket_id}", json={"status": "in_progress"}, headers=headers)
        assert p1.status_code == 200
        p2 = client.patch(f"/api/tickets/{ticket_id}", json={"status": "resolved"}, headers=headers)
        assert p2.status_code == 200
        agents_after = {a["name"]: a for a in client.get("/api/agents").json()}
        assert agents_after["Billing & Bundles Specialist"]["current_load"] == 0

        p3 = client.patch(f"/api/tickets/{ticket_id}", json={"status": "closed"}, headers=headers)
        assert p3.status_code == 200

        # Invalid transition from closed -> in_progress rejected with 409
        bad_trans = client.patch(f"/api/tickets/{ticket_id}", json={"status": "in_progress"}, headers=headers)
        assert bad_trans.status_code == 409


def test_wf4_admin_config_fr21_snapshot_isolation_and_kill_switch(api_env):
    app, cfg, state = api_env
    with TestClient(app) as client:
        admin_hdrs = _login(client, "admin@telecom.local", cfg.svr_bootstrap_password)

        # Ticket 1 created at default threshold 0.5 with confidence 0.72 -> READY
        state["prediction"] = _build_prediction(confidence=0.72)
        up1 = client.post(
            "/api/voicemails",
            files={"file": ("t1.wav", make_wav_bytes(1.2), "audio/wav")},
            headers=admin_hdrs,
        )
        assert up1.status_code == 202
        t1_id = up1.json()["ticket_id"]
        t1 = client.get(f"/api/tickets/{t1_id}").json()
        assert t1["confidence_threshold_snapshot"] == 0.5
        assert t1["status"] == "ready"

        # Admin raises threshold to 0.85 (FR21: applies to NEW tickets only)
        set_res = client.patch(
            "/api/settings",
            json={"confidence_threshold": 0.85},
            headers=admin_hdrs,
        )
        assert set_res.status_code == 200
        assert set_res.json()["confidence_threshold"] == 0.85

        # Ticket 2 created with same confidence 0.72 -> UNASSIGNED (low_confidence under 0.85)
        up2 = client.post(
            "/api/voicemails",
            files={"file": ("t2.wav", make_wav_bytes(1.8), "audio/wav")},
            headers=admin_hdrs,
        )
        assert up2.status_code == 202
        t2_id = up2.json()["ticket_id"]
        t2 = client.get(f"/api/tickets/{t2_id}").json()
        assert t2["confidence_threshold_snapshot"] == 0.85
        assert t2["status"] == "unassigned"
        assert t2["review_reason"] == "low_confidence"

        # Ticket 1 STILL retains its original 0.5 snapshot and ready status!
        t1_again = client.get(f"/api/tickets/{t1_id}").json()
        assert t1_again["confidence_threshold_snapshot"] == 0.5
        assert t1_again["status"] == "ready"

        # Admin creates & updates an agent
        ag_res = client.post(
            "/api/agents",
            json={"name": "Senior Retention Specialist", "skills": ["General"], "capacity": 4, "seed_order": 10},
            headers=admin_hdrs,
        )
        assert ag_res.status_code == 201
        ag_id = ag_res.json()["id"]
        ag_patch = client.patch(f"/api/agents/{ag_id}", json={"available": False}, headers=admin_hdrs)
        assert ag_patch.status_code == 200
        assert ag_patch.json()["available"] is False

        # Skill mapping rejects missing categories (< 11) with 422
        incomplete_skills = dict(DEFAULT_SKILL_MAPPING)
        incomplete_skills.pop("sim_services")
        bad_skills = client.put(
            "/api/settings/skills",
            json={"mappings": incomplete_skills},
            headers=admin_hdrs,
        )
        assert bad_skills.status_code == 422

        # Complete 11-category skill mapping succeeds
        ok_skills = client.put(
            "/api/settings/skills",
            json={"mappings": dict(DEFAULT_SKILL_MAPPING)},
            headers=admin_hdrs,
        )
        assert ok_skills.status_code == 200
        assert len(ok_skills.json()["mappings"]) == 11

        # Template update rejects unexpanded placeholders (S3)
        bad_tpl = client.put(
            "/api/settings/templates/sim_services",
            json={
                "template_ar": "مرحبا {customer_name}",
                "template_en": "Hello {customer_name}",
                "customer_request_ar": "طلب شريحة",
                "customer_request_en": "SIM request",
            },
            headers=admin_hdrs,
        )
        assert bad_tpl.status_code == 422

        ok_tpl = client.put(
            "/api/settings/templates/sim_services",
            json={
                "template_ar": "أهلا بحضرتك من فريق خدمات الشريحة، بنتواصل معاك لمتابعة طلبك.",
                "template_en": "Hello from SIM Care, we are calling to follow up on your SIM service request.",
                "customer_request_ar": "المشترك يطلب مساعدة في خدمات الشريحة.",
                "customer_request_en": "Subscriber requests SIM service support.",
            },
            headers=admin_hdrs,
        )
        assert ok_tpl.status_code == 200
        assert ok_tpl.json()["version"] == 2

        # PRD 10.5: Supervisor can toggle auto_routing_enabled kill switch, but cannot edit threshold
        client.post("/api/auth/logout", headers=admin_hdrs)
        sup_hdrs = _login(client, "supervisor@telecom.local", cfg.svr_bootstrap_password)

        forbid_thr = client.patch(
            "/api/settings",
            json={"confidence_threshold": 0.4},
            headers=sup_hdrs,
        )
        assert forbid_thr.status_code == 403

        kill_res = client.patch(
            "/api/settings",
            json={"auto_routing_enabled": False},
            headers=sup_hdrs,
        )
        assert kill_res.status_code == 200
        assert kill_res.json()["auto_routing_enabled"] is False


def test_security_sqli_rate_limit_csrf_idor_rbac_mass_assignment_and_headers(api_env):
    app, cfg, state = api_env

    # Add a synthetic route that raises an unhandled RuntimeError to verify generic 500 handler
    @app.get("/api/test-crash")
    def _boom():
        raise RuntimeError("SELECT * FROM secret_table WHERE key='top_secret_path_C:\\keys'")

    with TestClient(app, raise_server_exceptions=False) as client:
        # 1. Security headers + health check
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in health.headers

        # 2. Global exception handler leaks ZERO stack traces, SQL, or paths
        crash = client.get("/api/test-crash")
        assert crash.status_code == 500
        body = crash.json()
        assert body["detail"] == "Internal server error."
        assert "error_id" in body
        assert "SELECT" not in crash.text
        assert "secret_table" not in crash.text
        assert "Traceback" not in crash.text

        # 3. CORS rejects untrusted origin
        cors_preflight = client.options(
            "/api/health",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert cors_preflight.headers.get("access-control-allow-origin") != "https://evil.example"
        assert cors_preflight.headers.get("access-control-allow-origin") != "*"

        # 4. SQLi login attempt fails with generic error
        sqli = client.post(
            "/api/auth/login",
            json={"email": "' OR 1=1 --", "password": "anything"},
        )
        assert sqli.status_code == 401
        assert sqli.json()["detail"] == "Invalid email or password."

        # 5. Setup a ticket assigned to Network Care Specialist as supervisor
        sup_hdrs = _login(client, "supervisor@telecom.local", cfg.svr_bootstrap_password)
        state["prediction"] = _build_prediction(category="network_and_connectivity", confidence=0.92)
        up = client.post(
            "/api/voicemails",
            files={"file": ("net_only.wav", make_wav_bytes(1.1), "audio/wav")},
            headers=sup_hdrs,
        )
        assert up.status_code == 202
        net_ticket_id = up.json()["ticket_id"]
        net_vm_id = up.json()["voicemail_id"]

        # 6. Missing CSRF header on cookie-authenticated mutation -> 403
        no_csrf = client.patch(f"/api/tickets/{net_ticket_id}", json={"status": "in_progress"})
        assert no_csrf.status_code == 403
        assert "csrf" in no_csrf.json()["detail"].lower()

        # 7. Mass assignment extra fields -> 422
        mass_assign = client.patch(
            f"/api/tickets/{net_ticket_id}",
            json={"status": "in_progress", "organization_id": "other-org", "is_admin": True},
            headers=sup_hdrs,
        )
        assert mass_assign.status_code == 422

        client.post("/api/auth/logout", headers=sup_hdrs)

        # 8. IDOR & RBAC: Billing agent cannot view/play/patch Network agent's ticket or call admin endpoints
        billing_hdrs = _login(client, "billing.agent@telecom.local", cfg.svr_bootstrap_password)

        assert client.get(f"/api/tickets/{net_ticket_id}").status_code == 403
        assert client.get(f"/api/voicemails/{net_vm_id}/audio").status_code == 403
        assert (
            client.patch(
                f"/api/tickets/{net_ticket_id}",
                json={"status": "in_progress"},
                headers=billing_hdrs,
            ).status_code
            == 403
        )
        # List tickets as billing agent returns 0 (strictly scoped to own assigned_agent_id)
        list_as_billing = client.get("/api/tickets")
        assert list_as_billing.status_code == 200
        assert list_as_billing.json()["total"] == 0

        # Agent calling admin/supervisor endpoints -> 403
        assert (
            client.post(
                "/api/agents",
                json={"name": "Rogue", "skills": ["Network"], "capacity": 5},
                headers=billing_hdrs,
            ).status_code
            == 403
        )
        assert client.get("/api/settings").status_code == 403
        assert client.get("/api/audit-logs").status_code == 403
        assert (
            client.post(
                f"/api/tickets/{net_ticket_id}/correct",
                json={"complaint_urgency": "low"},
                headers=billing_hdrs,
            ).status_code
            == 403
        )

        # Network agent CAN view and transition their own ticket to in_progress -> resolved
        client.post("/api/auth/logout", headers=billing_hdrs)
        net_hdrs = _login(client, "network.agent@telecom.local", cfg.svr_bootstrap_password)
        assert client.get(f"/api/tickets/{net_ticket_id}").status_code == 200
        assert client.get(f"/api/voicemails/{net_vm_id}/audio").status_code == 200
        assert (
            client.patch(
                f"/api/tickets/{net_ticket_id}",
                json={"status": "in_progress"},
                headers=net_hdrs,
            ).status_code
            == 200
        )
        # Agent cannot reassign their own ticket
        assert (
            client.patch(
                f"/api/tickets/{net_ticket_id}",
                json={"unassign": True},
                headers=net_hdrs,
            ).status_code
            == 403
        )

        # 9. 20 rapid login attempts trigger 429 sliding-window rate limit + lockout
        client.post("/api/auth/logout", headers=net_hdrs)
        statuses = []
        for idx in range(20):
            r = client.post(
                "/api/auth/login",
                json={"email": f"attacker{idx % 3}@telecom.local", "password": "WrongPassword999!"},
            )
            statuses.append(r.status_code)
        assert 429 in statuses


def test_websocket_realtime_push_monitoring_export_and_pagination(api_env):
    app, cfg, state = api_env
    with TestClient(app) as client:
        # Unauthenticated WebSocket rejected with 4401
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/queue") as ws:
                ws.receive_json()

        sup_hdrs = _login(client, "supervisor@telecom.local", cfg.svr_bootstrap_password)

        # Create 2 tickets with different priorities for urgent-first sorting & cursor pagination
        state["prediction"] = _build_prediction(
            category="billing_and_charges",
            urgency="low",
            state="calm",
            churn="not_at_risk",
            confidence=0.91,
        )
        r_low = client.post(
            "/api/voicemails",
            files={"file": ("low.wav", make_wav_bytes(1.0), "audio/wav")},
            headers=sup_hdrs,
        )
        low_id = r_low.json()["ticket_id"]

        state["prediction"] = _build_prediction(
            category="network_and_connectivity",
            urgency="high",
            state="mad",
            churn="at_risk",
            confidence=0.94,
        )
        r_urgent = client.post(
            "/api/voicemails",
            files={"file": ("urgent.wav", make_wav_bytes(1.3), "audio/wav")},
            headers=sup_hdrs,
        )
        urgent_id = r_urgent.json()["ticket_id"]

        # Urgent-first ordering + cursor pagination (limit=1)
        page1 = client.get("/api/tickets", params={"limit": 1}).json()
        assert page1["total"] == 2
        assert page1["items"][0]["id"] == urgent_id
        assert page1["items"][0]["queue_priority"] == "urgent"
        assert page1["next_cursor"] is not None

        page2 = client.get("/api/tickets", params={"limit": 1, "cursor": page1["next_cursor"]}).json()
        assert page2["items"][0]["id"] == low_id
        assert page2["next_cursor"] is None

        # Authenticated WebSocket receives queue_snapshot, responds to ping, and receives live ticket_update
        with client.websocket_connect("/ws/queue") as ws:
            snap = ws.receive_json()
            assert snap["type"] == "queue_snapshot"
            assert snap["total_tickets"] == 2

            ws.send_text("ping")
            assert ws.receive_json() == {"type": "pong"}

            # Trigger live ticket update via PATCH
            patch_res = client.patch(
                f"/api/tickets/{urgent_id}",
                json={"status": "in_progress"},
                headers=sup_hdrs,
            )
            assert patch_res.status_code == 200

            evt = ws.receive_json()
            assert evt["type"] == "ticket_update"
            assert evt["ticket_id"] == urgent_id
            assert evt["status"] == "in_progress"

        # Monitoring summary, evaluation runs, Prometheus metrics, and audit log CSV/JSON export
        mon = client.get("/api/monitoring/summary")
        assert mon.status_code == 200
        mon_data = mon.json()
        assert mon_data["total_tickets"] == 2
        assert mon_data["tickets_last_24h"] == 2
        assert len(mon_data["confidence_histogram"]) == 10
        assert "transcribe" in mon_data["stage_latency_ms"]

        evals = client.get("/api/evaluation/runs")
        assert evals.status_code == 200
        assert isinstance(evals.json(), list)

        metrics = client.get("/api/metrics")
        assert metrics.status_code == 200
        assert "svr_http_requests_total" in metrics.text
        assert "svr_pipeline_runs_total" in metrics.text

        exp_csv = client.get("/api/audit-logs/export", params={"format": "csv"})
        assert exp_csv.status_code == 200
        assert "text/csv" in exp_csv.headers["content-type"]
        assert "entity_type" in exp_csv.text

        exp_json = client.get("/api/audit-logs/export", params={"format": "json"})
        assert exp_json.status_code == 200
        assert isinstance(exp_json.json(), list)

        # Verify 'exported' AuditEvent was recorded
        audit_logs = client.get("/api/audit-logs", params={"action": "exported"}).json()
        assert audit_logs["total"] >= 2
