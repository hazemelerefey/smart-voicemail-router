"""Regression unit tests reproducing and verifying fixes for #d18eb2ea, #249ab615, and #d7830282."""

from __future__ import annotations

import hashlib
from pathlib import Path

from svr_platform.config import Settings
from svr_platform.crypto import EncryptionService
from svr_platform.database import DatabaseManager
from svr_platform.models import AIInteractionLog, Agent, Organization, Ticket, User, Voicemail
from svr_platform.services.adjudicator import ClassificationAdjudicator
from svr_platform.services.agentic_gate import AgenticTranscriptGate
from svr_platform.services.classification import ClassificationResult
from svr_platform.services.memory import AgentMemoryService, LocalEmbeddingClient
from svr_platform.services.orchestrator import VoiceGateOrchestrator, is_weekly_quality_sample
from svr_platform.services.stt import STTResult
from svr_platform.services.transcript_gate import (
    GateResult,
    STTSignalSummary,
    TranscriptVerificationGate,
    strip_untrusted_transcript_tags,
    validate_candidate_transcript,
)
from svr_platform.taxonomy import TicketStatus, TRAINED_CLASSES_BY_FIELD
from tests.conftest import make_wav_bytes

TICKET_D18 = "d18eb2ea-087b-4f91-ae89-e747a991ef6c"
TICKET_249 = "249ab615-99a2-4bd4-9623-ee97fa1ea031"
TICKET_D78 = "d7830282-d813-4df9-9218-7e47110da61d"

RAW_TEXT_D18 = "المفروض لما بلغ عن فقدان شريحه يتم ايقافها فورا بس قعدت شغاله اكتر من 24 ساعه"
REPAIRED_TEXT_D18 = "المفروض لما بلغ عن فقدان شريحة يتم ايقافها فورا بس قعدت شغاله اكتر من 24 ساعه"


def _dist(field: str, winner: str, top_prob: float) -> dict[str, float]:
    classes = TRAINED_CLASSES_BY_FIELD[field]
    others = [c for c in classes if c != winner]
    rem = (1.0 - top_prob) / len(others)
    probs = {c: round(rem, 6) for c in others}
    probs[winner] = round(1.0 - sum(probs.values()), 6)
    return probs


def test_strip_untrusted_transcript_tags_and_gates_accept_tagged_echo() -> None:
    tagged = f"<untrusted_transcript>{REPAIRED_TEXT_D18}</untrusted_transcript>"
    assert strip_untrusted_transcript_tags(tagged) == REPAIRED_TEXT_D18
    assert strip_untrusted_transcript_tags(f"< UNTRUSTED_TRANSCRIPT >  {RAW_TEXT_D18} </untrusted_transcript>") == RAW_TEXT_D18

    ok_before, reason_before = validate_candidate_transcript(RAW_TEXT_D18, tagged)
    assert ok_before is False
    assert "unexpected_latin_injection" in str(reason_before)

    # AgenticTranscriptGate (LangGraph + direct loop) must strip echoed tags before validation
    reviewer = lambda ctx: {
        "thinking": "Fixed ta marbuta on SIM card word.",
        "corrected_text": tagged,
        "confidence": 0.85,
        "is_coherent": True,
        "changes": [{"from": "شريحه", "to": "شريحة", "reason": "taa_marbuta_drop"}],
    }
    agentic = AgenticTranscriptGate(reviewer_override=reviewer, fast_path_enabled=False)
    res_agentic = agentic.verify(
        RAW_TEXT_D18,
        min_avg_logprob=-0.0721,
        max_no_speech_prob=0.2488,
        force_audit=True,
    )
    assert res_agentic.status in ("corrected", "verified")
    assert res_agentic.needs_human_review is False
    assert "<untrusted_transcript>" not in res_agentic.final_text
    assert res_agentic.final_text == REPAIRED_TEXT_D18

    # TranscriptVerificationGate must also strip echoed wrapper tags
    direct_gate = TranscriptVerificationGate(reviewer_override=reviewer)
    res_direct = direct_gate.verify(
        RAW_TEXT_D18,
        min_avg_logprob=-0.1391,
        max_no_speech_prob=0.3791,
    )
    assert res_direct.status in ("corrected", "verified")
    assert res_direct.needs_human_review is False
    assert "<untrusted_transcript>" not in res_direct.final_text


def test_orchestrator_reaudit_zero_accept_does_not_downgrade_clean_ticket(
    db_manager: DatabaseManager,
    test_settings: Settings,
) -> None:
    crypto = EncryptionService(test_settings.svr_encryption_key)
    enc_dir = test_settings.svr_storage_dir / "voicemails"
    enc_dir.mkdir(parents=True, exist_ok=True)
    enc_path = enc_dir / "frustrated_0324.wav.enc"
    enc_path.write_bytes(crypto.encrypt_bytes(make_wav_bytes(1.5)))

    with db_manager.session_factory() as db:
        org = db.query(Organization).first()
        user = db.query(User).first()
        assert org is not None and user is not None

        vm = Voicemail(
            organization_id=org.id,
            file_name="frustrated_0324.wav",
            file_path=str(enc_path),
            format="wav",
            size_bytes=enc_path.stat().st_size,
            duration_seconds=6.757,
            sample_rate_hz=16000,
            channels=1,
            status=TicketStatus.PROCESSING.value,
            idempotency_key="test-d18eb2ea-reaudit-guard",
            content_sha256="0" * 64,
            encrypted=True,
            created_by=user.id,
        )
        db.add(vm)
        db.flush()

        ticket = Ticket(
            id=TICKET_D18,
            voicemail_id=vm.id,
            organization_id=org.id,
            status=TicketStatus.PROCESSING.value,
            needs_human_review=True,
        )
        db.add(ticket)
        db.commit()

        class _MockSTT:
            canonical_model_name = "cohere-mock"
            low_memory_mode = False

            def transcribe(self, _wav_or_path, file_name: str = "", **_kwargs) -> STTResult:
                return STTResult(
                    file=file_name or "frustrated_0324.wav",
                    model="cohere-mock",
                    text=RAW_TEXT_D18,
                    text_norm=RAW_TEXT_D18,
                    min_avg_logprob=-0.0721,
                    max_no_speech_prob=0.2488,
                    needs_review=False,
                    review_reasons="",
                    dup_text_size=1,
                    stt_confidence_source="logprob",
                    error="",
                )

        class _MockGateZeroAcceptReaudit:
            def verify(
                self,
                raw_text: str,
                *,
                min_avg_logprob: float | None = None,
                max_no_speech_prob: float | None = None,
                stt_review_reasons: str = "",
                stt_confidence_source: str = "logprob",
                force_audit: bool = False,
            ) -> GateResult:
                if not force_audit:
                    return GateResult(
                        agent_name="VoiceGate Orchestrator",
                        model="qwen2.5:3b",
                        backend_used="langgraph",
                        status="verified",
                        raw_text=raw_text,
                        final_text=raw_text,
                        final_text_norm=raw_text,
                        language_mix="arabic",
                        correction_applied=False,
                        rounds_run=0,
                        confidence=0.92,
                        convergence_reason="fast_path_clean_acoustic",
                        needs_human_review=False,
                        review_reason=None,
                        signal_summary={"acoustic_risk": "low", "lexical_flags": []},
                        latency_ms=3.0,
                    )
                return GateResult(
                    agent_name="VoiceGate Orchestrator",
                    model="qwen2.5:3b",
                    backend_used="langgraph",
                    status="uncertain",
                    raw_text=raw_text,
                    final_text=raw_text,
                    final_text_norm=raw_text,
                    language_mix="arabic",
                    correction_applied=False,
                    rounds_run=4,
                    confidence=0.0,
                    convergence_reason="max_iterations_exhausted",
                    needs_human_review=True,
                    review_reason="uncertain_transcript",
                    signal_summary={"acoustic_risk": "low", "lexical_flags": []},
                    latency_ms=10.0,
                )

        class _MockClassifier:
            base_model_id = "marbert-mock"

            def classify(self, _text_norm: str, *, confidence_threshold: float = 0.5, file_name: str = "") -> ClassificationResult:
                # Reproduces exact #d18eb2ea raw category prob (0.3688 < 0.45) and overall >= 0.50 after calibration
                return ClassificationResult(
                    labels={
                        "complaint_category": "sim_services",
                        "complaint_urgency": "medium",
                        "customer_state": "frustrated",
                        "churn_risk": "not_at_risk",
                    },
                    probabilities={
                        "complaint_category": _dist("complaint_category", "sim_services", 0.3688),
                        "complaint_urgency": _dist("complaint_urgency", "medium", 0.684149),
                        "customer_state": _dist("customer_state", "frustrated", 0.834383),
                        "churn_risk": _dist("churn_risk", "not_at_risk", 0.999177),
                    },
                    confidence=0.3688,
                    needs_human_review=True,
                    review_reason="low_confidence",
                    model_version="marbert-mock",
                    label_sources={
                        "complaint_category": "model",
                        "complaint_urgency": "model",
                        "customer_state": "model",
                        "churn_risk": "model",
                    },
                )

        class _MockAdjudicator:
            enabled = True
            ollama_model = "qwen2.5:3b"

            def review_and_adjudicate(self, _db, **_kwargs):
                class _AdjOut:
                    mode = "adjudicated"
                    changed_fields: list[str] = []
                    resolved_gate_uncertainty = False
                    latency_ms = 5.0
                    reasoning = "SIM card lost and remains active -> sim_services"
                    learned_lesson = ""
                    classification_result = ClassificationResult(
                        labels={
                            "complaint_category": "sim_services",
                            "complaint_urgency": "medium",
                            "customer_state": "frustrated",
                            "churn_risk": "not_at_risk",
                        },
                        probabilities={
                            "complaint_category": _dist("complaint_category", "sim_services", 0.542008),
                            "complaint_urgency": _dist("complaint_urgency", "medium", 0.684149),
                            "customer_state": _dist("customer_state", "frustrated", 0.834383),
                            "churn_risk": _dist("churn_risk", "not_at_risk", 0.999177),
                        },
                        confidence=0.542008,
                        needs_human_review=False,
                        review_reason=None,
                        model_version="marbert-mock+vg-adjudicator",
                        label_sources={
                            "complaint_category": "model",
                            "complaint_urgency": "model",
                            "customer_state": "model",
                            "churn_risk": "model",
                        },
                    )

                    def to_report_dict(self) -> dict:
                        return {
                            "mode": self.mode,
                            "calibrated_confidence": 0.542008,
                            "resolved_gate_uncertainty": False,
                            "escalate_to_human": False,
                        }

                return _AdjOut()

        orchestrator = VoiceGateOrchestrator(
            crypto=crypto,
            stt_service=_MockSTT(),  # type: ignore[arg-type]
            transcript_gate=_MockGateZeroAcceptReaudit(),  # type: ignore[arg-type]
            classifier_service=_MockClassifier(),  # type: ignore[arg-type]
            adjudicator=_MockAdjudicator(),  # type: ignore[arg-type]
            adaptive_reaudit_enabled=True,
            adaptive_reaudit_category_threshold=0.45,
        )
        updated = orchestrator.run(db, ticket_id=TICKET_D18)

        network_agent = db.query(Agent).filter(Agent.name == "Network Care Specialist").one()
        assert updated.status == TicketStatus.READY.value
        assert updated.assigned_agent_id == network_agent.id
        assert updated.needs_human_review is False
        assert updated.review_reason is None
        assert updated.stage_status.get("verify_transcript") == "ok"
        reaudit_logs = (
            db.query(AIInteractionLog)
            .filter(AIInteractionLog.ticket_id == TICKET_D18, AIInteractionLog.stage == "verify_transcript_reaudit")
            .all()
        )
        assert len(reaudit_logs) == 1


def test_adjudicator_resolves_gate_uncertainty_at_org_threshold_050(
    db_manager: DatabaseManager,
) -> None:
    mem = AgentMemoryService(embed_client=LocalEmbeddingClient(use_ollama=False), enabled=True)
    adjudicator = ClassificationAdjudicator(
        memory_service=mem,
        enabled=True,
        adjudicator_override=lambda _payload: {
            "reasoning": "SIM card loss replacement is sim_services.",
            "complaint_category": "sim_services",
            "complaint_urgency": "medium",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
            "field_confidences": {
                "complaint_category": 0.64,
                "complaint_urgency": 0.75,
                "customer_state": 0.85,
                "churn_risk": 0.99,
            },
            "escalate_to_human": False,
            "learned_lesson": "",
        },
    )

    marbert_res = ClassificationResult(
        labels={
            "complaint_category": "sim_services",
            "complaint_urgency": "medium",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
        },
        probabilities={
            "complaint_category": _dist("complaint_category", "sim_services", 0.3688),
            "complaint_urgency": _dist("complaint_urgency", "medium", 0.684149),
            "customer_state": _dist("customer_state", "frustrated", 0.834383),
            "churn_risk": _dist("churn_risk", "not_at_risk", 0.999177),
        },
        confidence=0.3688,
        needs_human_review=True,
        review_reason="low_confidence",
        model_version="marbert-mock",
        label_sources={
            "complaint_category": "model",
            "complaint_urgency": "model",
            "customer_state": "model",
            "churn_risk": "model",
        },
    )
    uncertain_gate = GateResult(
        agent_name="VoiceGate Orchestrator",
        model="qwen2.5:3b",
        backend_used="langgraph",
        status="uncertain",
        raw_text=RAW_TEXT_D18,
        final_text=RAW_TEXT_D18,
        final_text_norm=RAW_TEXT_D18,
        language_mix="arabic",
        correction_applied=False,
        rounds_run=4,
        confidence=0.0,
        convergence_reason="max_iterations_exhausted",
        needs_human_review=True,
        review_reason="uncertain_transcript",
        signal_summary={"acoustic_risk": "low", "lexical_flags": []},
    )

    with db_manager.session_factory() as db:
        org = db.query(Organization).first()
        assert org is not None
        res = adjudicator.review_and_adjudicate(
            db,
            organization_id=org.id,
            ticket_id=TICKET_D18,
            transcript=RAW_TEXT_D18,
            text_norm=RAW_TEXT_D18,
            marbert_result=marbert_res,
            gate_result=uncertain_gate,
            confidence_threshold=0.50,
        )
        assert res.mode == "adjudicated"
        assert 0.50 <= res.classification_result.confidence < 0.55
        assert res.resolved_gate_uncertainty is True


def test_weekly_quality_sample_deterministic_buckets_for_three_tickets() -> None:
    assert int(hashlib.sha256(TICKET_249.encode("utf-8")).hexdigest()[:8], 16) % 1000 == 7
    assert int(hashlib.sha256(TICKET_D78.encode("utf-8")).hexdigest()[:8], 16) % 1000 == 10
    assert int(hashlib.sha256(TICKET_D18.encode("utf-8")).hexdigest()[:8], 16) % 1000 == 170

    assert is_weekly_quality_sample(TICKET_249, 0.05) is True
    assert is_weekly_quality_sample(TICKET_D78, 0.05) is True
    assert is_weekly_quality_sample(TICKET_D18, 0.05) is False


def test_reprocess_tickets_cli_requires_explicit_ids(tmp_path: Path) -> None:
    import importlib.util

    script_path = Path(__file__).resolve().parents[2] / "ops" / "reprocess_tickets.py"
    spec = importlib.util.spec_from_file_location("reprocess_tickets", script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Missing arguments -> non-zero refusal
    assert mod.main([]) == 2
    # Empty --ticket-ids -> non-zero refusal
    assert mod.main(["--ticket-ids"]) == 2
    # Wildcards -> non-zero refusal
    assert mod.main(["--ticket-ids", "all"]) == 2
    assert mod.main(["--ticket-ids", "*"]) == 2
    # Nonexistent ID -> non-zero refusal without touching DB
    db_file = tmp_path / "empty.db"
    DatabaseManager(f"sqlite:///{db_file.as_posix()}").create_all()
    assert mod.main(["--database-url", f"sqlite:///{db_file.as_posix()}", "--ticket-ids", TICKET_D18]) == 2


def test_clean_sampled_ticket_tracks_qa_without_human_review_and_models_telemetry(
    db_manager: DatabaseManager,
    test_settings: Settings,
) -> None:
    from fastapi.testclient import TestClient
    from svr_platform.api.main import create_app

    crypto = EncryptionService(test_settings.svr_encryption_key)
    enc_dir = test_settings.svr_storage_dir / "voicemails"
    enc_dir.mkdir(parents=True, exist_ok=True)
    enc_path = enc_dir / "frustrated_0014.wav.enc"
    enc_path.write_bytes(crypto.encrypt_bytes(make_wav_bytes(1.5)))

    with db_manager.session_factory() as db:
        org = db.query(Organization).first()
        user = db.query(User).first()
        assert org is not None and user is not None

        vm = Voicemail(
            organization_id=org.id,
            file_name="frustrated_0014.wav",
            file_path=str(enc_path),
            format="wav",
            size_bytes=enc_path.stat().st_size,
            duration_seconds=5.9,
            sample_rate_hz=16000,
            channels=1,
            status=TicketStatus.PROCESSING.value,
            idempotency_key="test-249-qa-non-blocking",
            content_sha256="1" * 64,
            encrypted=True,
            created_by=user.id,
        )
        db.add(vm)
        db.flush()
        ticket = Ticket(
            id=TICKET_249,  # bucket = 7 < 50 (in 5% sample)
            voicemail_id=vm.id,
            organization_id=org.id,
            status=TicketStatus.PROCESSING.value,
            needs_human_review=True,
        )
        db.add(ticket)
        db.commit()

        class _MockCleanSTT:
            canonical_model_name = "cohere-mock"
            device = "cuda"
            low_memory_mode = False

            def transcribe(self, _wav_or_path, file_name: str = "", **_kwargs) -> STTResult:
                return STTResult(
                    file=file_name or "frustrated_0014.wav",
                    model="cohere-mock",
                    text="لما بستخدم باقة اليومية ساعات بتشتغل وساعات لأ",
                    text_norm="لما بستخدم باقه اليوميه ساعات بتشتغل وساعات لا",
                    min_avg_logprob=-0.09,
                    max_no_speech_prob=0.12,
                    needs_review=False,
                    review_reasons="",
                    dup_text_size=1,
                    stt_confidence_source="logprob",
                    error="",
                )

        class _MockCleanClassifier:
            base_model_id = "marbert-mock"

            def has_local_checkpoints(self) -> bool:
                return True

            def classify(self, _text_norm: str, *, confidence_threshold: float = 0.5, file_name: str = "") -> ClassificationResult:
                return ClassificationResult(
                    labels={
                        "complaint_category": "balance_and_data",
                        "complaint_urgency": "medium",
                        "customer_state": "calm",
                        "churn_risk": "not_at_risk",
                    },
                    probabilities={
                        "complaint_category": _dist("complaint_category", "balance_and_data", 0.88),
                        "complaint_urgency": _dist("complaint_urgency", "medium", 0.82),
                        "customer_state": _dist("customer_state", "calm", 0.86),
                        "churn_risk": _dist("churn_risk", "not_at_risk", 0.99),
                    },
                    confidence=0.82,
                    needs_human_review=False,
                    review_reason=None,
                    model_version="marbert-mock",
                    label_sources={f: "model" for f in ("complaint_category", "complaint_urgency", "customer_state", "churn_risk")},
                )

        gate = AgenticTranscriptGate(
            reviewer_override=lambda ctx: {
                "thinking": "clean",
                "corrected_text": ctx["current_text"],
                "confidence": 0.94,
                "is_coherent": True,
                "changes": [],
            },
            fast_path_enabled=True,
        )
        stt = _MockCleanSTT()
        clf = _MockCleanClassifier()
        orchestrator = VoiceGateOrchestrator(
            crypto=crypto,
            stt_service=stt,  # type: ignore[arg-type]
            transcript_gate=gate,
            classifier_service=clf,  # type: ignore[arg-type]
        )
        updated = orchestrator.run(db, ticket_id=TICKET_249)
        assert updated.status == TicketStatus.READY.value
        assert updated.needs_human_review is False
        assert updated.review_reason is None
        assert updated.config_snapshot.get("qa_sampled") is True
        assert updated.config_snapshot.get("qa_sample_reason") == "weekly_quality_sample"

    app = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=stt,  # type: ignore[arg-type]
        transcript_gate=gate,
        classifier_service=clf,  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        assert login.status_code == 200
        summary = client.get("/api/monitoring/summary").json()
        assert summary["human_review_rate"] == 0.0
        assert summary["qa_sampled_count"] == 1
        assert summary["qa_sample_rate"] == 1.0

        models_res = client.get("/api/monitoring/models")
        assert models_res.status_code == 200, models_res.text
        m = models_res.json()
        assert m["escalated_human_review_count"] == 0
        assert m["qa_sampled_count"] == 1
        assert len(m["cohere_asr"]["recent_results"]) == 1
        assert len(m["marbert_v2"]["recent_results"]) == 1
        assert len(m["voicegate_orchestrator"]["recent_results"]) == 1
