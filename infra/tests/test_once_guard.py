import hashlib
import json

import pytest

from infra.once_guard import (
    ENTRY_KEYS,
    AlreadyEvaluatedError,
    EvaluationClaim,
    GuardError,
    claim_test_evaluation,
    file_sha256,
    is_claimed,
    normalize_model_name,
    read_log,
)

CHECKPOINT_A = "a" * 64
CHECKPOINT_B = "b" * 64


def claim(tmp_path, **overrides):
    args = dict(model="MARBERTv2", dataset_version="v2", run_id="test-001")
    args.update(overrides)
    return claim_test_evaluation(tmp_path / "runs" / "test_evaluations.json", **args)


def log(tmp_path):
    return read_log(tmp_path / "runs" / "test_evaluations.json")


def test_the_first_claim_is_recorded(tmp_path):
    c = claim(tmp_path, checkpoint_sha256=CHECKPOINT_A, now_utc="2026-11-21T10:00:00+00:00")
    assert isinstance(c, EvaluationClaim) and not c.consumed
    entries = log(tmp_path)["entries"]
    assert len(entries) == 1
    assert list(entries[0]) == list(ENTRY_KEYS)
    assert entries[0]["model"] == "MARBERTv2" and entries[0]["model_key"] == "marbertv2"
    assert entries[0]["dataset_version"] == "v2" and entries[0]["run_id"] == "test-001"
    assert entries[0]["checkpoint_sha256"] == CHECKPOINT_A
    assert entries[0]["uses"] == 1
    assert entries[0]["claimed_utc"] == "2026-11-21T10:00:00+00:00"


def test_the_same_model_and_version_is_refused_and_the_log_is_unchanged(tmp_path):
    claim(tmp_path)
    before = (tmp_path / "runs" / "test_evaluations.json").read_bytes()
    with pytest.raises(AlreadyEvaluatedError, match="already evaluated"):
        claim(tmp_path, run_id="test-002")
    assert (tmp_path / "runs" / "test_evaluations.json").read_bytes() == before
    assert len(log(tmp_path)["entries"]) == 1


def test_another_checkpoint_of_the_same_model_does_not_get_a_second_try(tmp_path):
    claim(tmp_path, checkpoint_sha256=CHECKPOINT_A)
    with pytest.raises(AlreadyEvaluatedError):
        claim(tmp_path, run_id="test-002", checkpoint_sha256=CHECKPOINT_B)
    assert len(log(tmp_path)["entries"]) == 1


def test_a_different_spelling_of_the_model_name_is_the_same_model(tmp_path):
    claim(tmp_path, model="MARBERTv2")
    for spelling in ["UBC-NLP/MARBERTv2", "marbertv2", "MARBERT-v2", " MARBERTv2 "]:
        with pytest.raises(AlreadyEvaluatedError):
            claim(tmp_path, model=spelling, run_id="test-002")


def test_the_model_name_is_normalized():
    assert normalize_model_name("UBC-NLP/MARBERTv2") == "marbertv2"
    assert normalize_model_name("faisalq/EgyBERT") == "egybert"
    assert normalize_model_name("EgyBERT") == "egybert"
    for bad in ["", "  ", None, 5, "///", "--"]:
        with pytest.raises(GuardError):
            normalize_model_name(bad)


def test_a_different_model_is_allowed(tmp_path):
    claim(tmp_path, model="MARBERTv2")
    claim(tmp_path, model="EgyBERT", run_id="test-002")
    assert [e["model_key"] for e in log(tmp_path)["entries"]] == ["marbertv2", "egybert"]


def test_a_new_dataset_version_allows_one_new_evaluation(tmp_path):
    claim(tmp_path, dataset_version="v2")
    claim(tmp_path, dataset_version="v3", run_id="test-002")
    with pytest.raises(AlreadyEvaluatedError):
        claim(tmp_path, dataset_version="v3", run_id="test-003")
    assert is_claimed(tmp_path / "runs" / "test_evaluations.json", "UBC-NLP/MARBERTv2", "v3")
    assert not is_claimed(tmp_path / "runs" / "test_evaluations.json", "MARBERTv2", "v4")


def test_a_claim_is_used_once_by_default(tmp_path):
    c = claim(tmp_path)
    c.consume()
    assert c.consumed and c.remaining == 0
    with pytest.raises(GuardError, match="no uses left"):
        c.consume()


def test_a_claim_covers_one_scoring_call_per_seed_and_no_more(tmp_path):
    c = claim(tmp_path, uses=5)
    assert log(tmp_path)["entries"][0]["uses"] == 5
    for _ in range(5):
        c.consume()
    assert c.consumed
    with pytest.raises(GuardError, match="5 were allowed"):
        c.consume()


@pytest.mark.parametrize("bad", [0, -1, 1.5, "5", None, True])
def test_bad_uses_are_refused_and_nothing_is_recorded(tmp_path, bad):
    with pytest.raises(GuardError, match="uses"):
        claim(tmp_path, uses=bad)
    assert not (tmp_path / "runs" / "test_evaluations.json").exists()


def test_the_test_file_hash_is_recorded_without_reading_labels(tmp_path):
    csv = tmp_path / "clean_training_test.csv"
    csv.write_bytes(b"audio_file,text_norm\nx.wav,DUMMY TEXT\n")
    claim(tmp_path, test_csv_path=csv)
    entry = log(tmp_path)["entries"][0]
    assert entry["test_file_sha256"] == hashlib.sha256(csv.read_bytes()).hexdigest()
    assert "DUMMY" not in (tmp_path / "runs" / "test_evaluations.json").read_text(encoding="utf-8")
    assert file_sha256(csv) == entry["test_file_sha256"]


def test_a_missing_test_file_is_an_error_and_nothing_is_recorded(tmp_path):
    with pytest.raises(GuardError, match="not found"):
        claim(tmp_path, test_csv_path=tmp_path / "nope.csv")
    assert not (tmp_path / "runs" / "test_evaluations.json").exists()


@pytest.mark.parametrize(
    "bad",
    [
        dict(run_id="../x"), dict(run_id=""), dict(run_id="a b"), dict(run_id=None),
        dict(dataset_version=""), dict(dataset_version=None),
        dict(model=""), dict(model=None),
        dict(checkpoint_sha256="xyz"), dict(checkpoint_sha256="a" * 63), dict(checkpoint_sha256=5),
    ],
)
def test_bad_arguments_are_refused_and_nothing_is_recorded(tmp_path, bad):
    with pytest.raises(GuardError):
        claim(tmp_path, **bad)
    assert not (tmp_path / "runs" / "test_evaluations.json").exists()


def test_a_damaged_log_is_an_error_and_is_not_overwritten(tmp_path):
    path = tmp_path / "runs" / "test_evaluations.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(GuardError, match="not valid JSON"):
        claim(tmp_path)
    assert path.read_text(encoding="utf-8") == "{not json"


@pytest.mark.parametrize(
    "content",
    [
        {"schema_version": 1},
        {"schema_version": 2, "entries": []},
        {"schema_version": 1, "entries": "x"},
        {"schema_version": 1, "entries": [{"model": "m"}]},
        [1, 2],
    ],
)
def test_a_log_in_a_wrong_shape_is_refused(tmp_path, content):
    path = tmp_path / "runs" / "test_evaluations.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(GuardError):
        claim(tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == content


def test_no_temporary_file_is_left_behind(tmp_path):
    claim(tmp_path)
    claim(tmp_path, model="EgyBERT", run_id="test-002")
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == ["test_evaluations.json"]


def test_a_missing_log_is_an_empty_log(tmp_path):
    assert read_log(tmp_path / "nope.json") == {"schema_version": 1, "entries": []}