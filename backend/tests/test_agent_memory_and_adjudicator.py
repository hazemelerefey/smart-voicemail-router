"""Unit and integration tests for VoiceGate Context Layer, 4-Layer Memory, and Classification Adjudicator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import make_wav_bytes
from svr_platform.api.main import create_app
from svr_platform.models import MemoryEpisode, Organization
from svr_platform.services.adjudicator import ClassificationAdjudicator
from svr_platform.services.agentic_gate import AgenticTranscriptGate
from svr_platform.services.classification import MARBERTv2ClassifierService
from svr_platform.services.context_layer import ContextAssembler
from svr_platform.services.memory import AgentMemoryService, LocalEmbeddingClient
from svr_platform.services.stt import WhisperSTTService
from svr_platform.taxonomy import TRAINED_CLASSES_BY_FIELD


def _dist(classes: list[str], winner: str, p_win: float = 0.88) -> dict[str, float]:
    rest = (1.0 - p_win) / (len(classes) - 1)
    probs = {c: round(rest, 6) for c in classes if c != winner}
    probs[winner] = round(1.0 - sum(probs.values()), 6)
    return probs


def _pred_map(
    *,
    category: str,
    cat_prob: float,
    urgency: str = "medium",
    urg_prob: float = 0.85,
    state: str = "frustrated",
    state_prob: float = 0.85,
    churn: str = "not_at_risk",
    churn_prob: float = 0.90,
) -> dict[str, dict[str, Any]]:
    return {
        "complaint_category": {
            "label": category,
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_category"], category, cat_prob),
        },
        "complaint_urgency": {
            "label": urgency,
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["complaint_urgency"], urgency, urg_prob),
        },
        "customer_state": {
            "label": state,
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["customer_state"], state, state_prob),
        },
        "churn_risk": {
            "label": churn,
            "probabilities": _dist(TRAINED_CLASSES_BY_FIELD["churn_risk"], churn, churn_prob),
        },
    }


def test_memory_seeding_rejects_val_and_test_splits_and_retrieves_knn(db_manager, test_settings, tmp_path: Path):
    mem = AgentMemoryService(embed_client=LocalEmbeddingClient(use_ollama=False), enabled=True)
    with db_manager.session_factory() as db:
        org = db.query(Organization).first()
        assert org is not None
        mem.ensure_default_semantic_and_procedural_memory(db, org.id)
        stats = mem.get_memory_stats(db, org.id)
        assert stats["semantic_entries_count"] >= 6
        assert stats["procedural_rules_active_count"] >= 4

        val_csv = tmp_path / "clean_training_val.csv"
        val_csv.write_text("audio_file,text_norm,complaint_category,complaint_urgency,customer_state,churn_risk\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Leakage guard"):
            mem.seed_episodic_memory_from_train(db, org.id, val_csv)

        test_csv = tmp_path / "clean_training_test.csv"
        test_csv.write_text("audio_file,text_norm,complaint_category,complaint_urgency,customer_state,churn_risk\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Leakage guard"):
            mem.seed_episodic_memory_from_train(db, org.id, test_csv)

        train_csv = tmp_path / "clean_training_train.csv"
        train_csv.write_text(
            "audio_file,text,text_norm,complaint_category,complaint_urgency,customer_state,churn_risk\n"
            "a1.wav,عايز اطلع شريحة بدل فاقد فورا,عايز اطلع شريحة بدل فاقد فورا,sim_services,high,frustrated,not_at_risk\n"
            "a2.wav,لو متحلتش هلغي الخط وهغير الشركة,لو متحلتش هلغي الخط وهغير الشركة,billing_and_charges,high,mad,at_risk\n",
            encoding="utf-8",
        )
        inserted = mem.seed_episodic_memory_from_train(db, org.id, train_csv)
        assert inserted == 2

        knn_res = mem.retrieve_similar_episodes(
            db, org.id, "موبايلي اتسرق وعايز اطلع شريحة بدل فاقد", top_k=3
        )
        assert knn_res.episodes
        assert knn_res.episodes[0].final_labels["complaint_category"] == "sim_services"
        assert knn_res.knn_votes["complaint_category"]["sim_services"] > 0.5


def test_adjudicator_fixes_wrong_marbert_and_learns_from_supervisor_feedback(db_manager, test_settings):
    mem = AgentMemoryService(embed_client=LocalEmbeddingClient(use_ollama=False), enabled=True)

    # Override simulates local Qwen fixing wrong cancellation_request -> sim_services & churn cue
    def _mock_adjudicator(payload: dict[str, Any]) -> dict[str, Any]:
        text_val = payload.get("voicemail_transcript", "")
        assert "<untrusted_transcript>" in text_val
        assert "domain_taxonomy_rules_semantic_memory" in payload
        return {
            "complaint_category": "sim_services",
            "complaint_urgency": "high",
            "customer_state": "frustrated",
            "churn_risk": "not_at_risk",
            "field_confidences": {
                "complaint_category": 0.89,
                "complaint_urgency": 0.86,
                "customer_state": 0.84,
                "churn_risk": 0.92,
            },
            "reasoning": "SIM block for lost phone + replacement is sim_services, not cancellation.",
            "escalate_to_human": False,
            "learned_lesson": "Lost phone requesting replacement SIM maps to sim_services.",
        }

    adjudicator = ClassificationAdjudicator(
        memory_service=mem,
        context_assembler=ContextAssembler(),
        enabled=True,
        low_memory_mode=False,
        adjudicator_override=_mock_adjudicator,
    )

    app = create_app(
        settings=test_settings,
        db_manager=db_manager,
        stt_service=WhisperSTTService(
            transcriber_override=lambda _b, _f: {
                "text": "لو سمحت موبايلي اتسرق وعايز اوقف الشريحة واطلع بدل فاقد",
                "min_avg_logprob": -0.25,
                "max_no_speech_prob": 0.08,
            }
        ),
        transcript_gate=AgenticTranscriptGate(
            fast_path_enabled=False,
            reviewer_override=lambda ctx: {
                "thinking": "Coherent Arabic complaint, minor uncertainty",
                "corrected_text": ctx["current_text"],
                "confidence": 0.72,
                "is_coherent": True,
                "changes": [],
            },
            max_iterations=1,
        ),
        classifier_service=MARBERTv2ClassifierService(
            models_dir=test_settings.svr_models_dir,
            repo_root=test_settings.repo_root,
            allow_validated_artifact_fallback=False,
            predictor_override=lambda _tn: _pred_map(
                category="cancellation_request",
                cat_prob=0.58,
                urgency="medium",
                urg_prob=0.60,
            ),
        ),
        memory_service=mem,
        adjudicator=adjudicator,
    )

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "supervisor@telecom.local", "password": test_settings.svr_bootstrap_password},
        )
        assert login.status_code == 200
        headers = {"X-CSRF-Token": client.cookies["svr_csrf"]}

        up = client.post(
            "/api/voicemails",
            files={"file": ("sim_swap.wav", make_wav_bytes(1.5), "audio/wav")},
            headers={**headers, "Idempotency-Key": "adj-sim-swap-01"},
        )
        assert up.status_code == 202
        ticket_id = up.json()["ticket_id"]

        detail = client.get(f"/api/tickets/{ticket_id}").json()
        assert detail["status"] == "ready"
        assert detail["complaint_category"] == "sim_services"
        assert detail["complaint_urgency"] == "high"
        assert detail["label_sources"]["complaint_category"] == "agent"
        assert detail["label_sources"]["complaint_urgency"] == "agent"
        assert detail["label_sources"]["customer_state"] == "model"
        assert abs(sum(detail["probabilities"]["complaint_category"].values()) - 1.0) <= 0.001
        assert detail["confidence"] >= 0.50

        tv = detail["transcript_verification"] or {}
        adj_meta = tv.get("orchestrator_adjudication") or {}
        assert adj_meta["mode"] == "adjudicated"
        assert "complaint_category" in adj_meta["changed_fields"]
        assert adj_meta["resolved_gate_uncertainty"] is True

        # Check memory stats & export endpoints before & after supervisor correction
        stats1 = client.get("/api/agent/memory/stats").json()
        assert stats1["episodic_total"] >= 1
        assert stats1["training_feedback_by_tier"].get("silver_agent", 0) >= 1

        corr = client.post(
            f"/api/tickets/{ticket_id}/correct",
            json={
                "customer_state": "mad",
                "note": "Caller urgently lost phone and sounded mad.",
            },
            headers=headers,
        )
        assert corr.status_code == 200

        stats2 = client.get("/api/agent/memory/stats").json()
        assert stats2["episodic_by_source"].get("human_correction", 0) >= 1
        assert stats2["training_feedback_by_tier"].get("gold_human", 0) >= 1

        exp_jsonl = client.get("/api/agent/memory/training-export?format=jsonl")
        assert exp_jsonl.status_code == 200
        rows = [json.loads(line) for line in exp_jsonl.text.strip().splitlines() if line.strip()]
        assert any(r["quality_tier"] == "gold_human" and r["customer_state"] == "mad" for r in rows)
