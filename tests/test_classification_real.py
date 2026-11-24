"""Tests for real and extensible classification stage."""

import pytest
from svr.schemas import (
    AudioEvidence,
    ChurnRisk,
    ComplaintCategory,
    ComplaintUrgency,
    CustomerState,
    TextAnalysis,
)
from svr.stages import classification
from svr.stages.intake import AudioMeta
from svr.pipeline import run_pipeline


@pytest.fixture
def sample_audio_evidence():
    return AudioEvidence(
        voicemail_id="vm-test-101",
        audio_path_local=None,
        duration_s=15.0,
        format="wav",
        sample_rate_hz=16000,
        channels=1,
        transcript="عندي مشكلة في الفاتورة والمبلغ كبير جدا وبفكر اغير الشركة",
        stt_provider="test",
        stt_model_version="test-1",
        stt_confidence=0.95,
        language_mix=None,
        audio_quality={"mock": False},
    )


def test_classify_fallback_to_mock_when_no_model(sample_audio_evidence):
    analysis = classification.classify(sample_audio_evidence)
    assert isinstance(analysis, TextAnalysis)
    assert analysis.voicemail_id == sample_audio_evidence.voicemail_id
    assert analysis.complaint_category is not None


def test_classify_with_empty_transcript(sample_audio_evidence):
    sample_audio_evidence.transcript = ""
    # With a dummy model registered
    def dummy_fn(text):
        return {}
    analysis = classification.classify(sample_audio_evidence, classifier_fn=dummy_fn)
    assert analysis.needs_human_review is True
    assert analysis.complaint_category is None


def test_classify_with_real_model_predictions(sample_audio_evidence):
    def real_model_fn(text):
        return {
            "complaint_category": ComplaintCategory.BILLING_AND_CHARGES,
            "complaint_urgency": ComplaintUrgency.HIGH,
            "customer_state_text": CustomerState.MAD,
            "churn_risk": ChurnRisk.AT_RISK,
            "confidence": 0.92,
            "summary": "العميل يشتكي من ارتفاع الفاتورة ويهدد بإلغاء الخدمة.",
        }

    analysis = classification.classify(sample_audio_evidence, classifier_fn=real_model_fn)
    assert analysis.complaint_category == ComplaintCategory.BILLING_AND_CHARGES
    assert analysis.complaint_urgency == ComplaintUrgency.HIGH
    assert analysis.customer_state_text == CustomerState.MAD
    assert analysis.churn_risk == ChurnRisk.AT_RISK
    assert analysis.confidence == 0.92
    assert analysis.needs_human_review is False


def test_classify_low_confidence_requires_review(sample_audio_evidence):
    def uncertain_model_fn(text):
        return {
            "complaint_category": ComplaintCategory.OTHER,
            "complaint_urgency": ComplaintUrgency.LOW,
            "customer_state_text": CustomerState.CALM,
            "churn_risk": ChurnRisk.NOT_AT_RISK,
            "confidence": 0.45,
        }

    analysis = classification.classify(sample_audio_evidence, classifier_fn=uncertain_model_fn)
    assert analysis.needs_human_review is True


def test_pipeline_with_custom_classification_fn():
    meta = AudioMeta(
        filename="test.wav",
        size_bytes=1000,
        duration_s=10.0,
        duration_checked=True,
        voicemail_id="vm-pipe-test",
        format="wav",
        sample_rate_hz=16000,
        channels=1,
    )

    def custom_classifier(audio):
        return TextAnalysis(
            voicemail_id=audio.voicemail_id,
            summary="شكوى فواتير عاجلة",
            complaint_category=ComplaintCategory.BILLING_AND_CHARGES,
            complaint_urgency=ComplaintUrgency.HIGH,
            customer_state_text=CustomerState.FRUSTRATED,
            churn_risk=ChurnRisk.AT_RISK,
            keywords=["فاتورة", "مبلغ"],
            customer_request="مراجعة الفاتورة",
            language_mix=None,
            suggested_script="أهلاً بك، سنقوم بمراجعة الفاتورة فوراً.",
            confidence=0.95,
            needs_human_review=False,
            schema_version=1,
            label_version="taxonomy-2026-11-15",
        )

    res = run_pipeline(meta, "vm-pipe-test", classification_fn=custom_classifier)
    assert res.ticket.complaint_category == ComplaintCategory.BILLING_AND_CHARGES
    assert res.ticket.complaint_urgency == ComplaintUrgency.HIGH
    assert res.ticket.churn_risk == ChurnRisk.AT_RISK
    # Should receive high/urgent queue priority due to urgency=3, churn=2, state=1 -> score=6
    assert res.decision.queue_priority.value == "urgent"
