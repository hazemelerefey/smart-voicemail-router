"""Single-task MARBERTv2 four-field classification service (FR6-FR8, AI1-AI3, S3, S4)."""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..taxonomy import ALLOWED_CLASSES_BY_FIELD, TRAINED_CLASSES_BY_FIELD

logger = logging.getLogger("svr_platform.classification")

CLASSIFICATION_FIELDS = (
    "complaint_category",
    "complaint_urgency",
    "customer_state",
    "churn_risk",
)
PROB_SUM_TOLERANCE = 0.001  # FR6: probabilities for a field shall sum to 1 within 0.001
MAX_SEQ_LEN = 128  # Fixed MARBERTv2 protocol (AI1)


@dataclass
class ClassificationResult:
    labels: dict[str, str | None]
    probabilities: dict[str, dict[str, float]]
    confidence: float
    needs_human_review: bool
    review_reason: str | None
    model_version: str
    rejected_labels: dict[str, str] = field(default_factory=dict)
    label_sources: dict[str, str] = field(default_factory=dict)
    error: str = ""


def discover_single_task_checkpoints(models_dir: Path, seed: int = 42) -> dict[str, Path] | None:
    """Locate 4 single-task MARBERTv2 checkpoint directories under models_dir.

    Supports both flat layout (<models_dir>/<field>/) and Sira's Drive handoff layout
    (<models_dir>/seed_<seed>/<field>/epoch_* or <models_dir>/seed_<seed>/<field>/).
    """
    if not models_dir or not models_dir.is_dir():
        return None

    found: dict[str, Path] = {}
    for field_name in CLASSIFICATION_FIELDS:
        candidates = [
            models_dir / field_name,
            models_dir / f"seed_{seed}" / field_name,
        ]
        # Also search epoch_* subdirectories under seed_<seed>/<field>
        seed_field_dir = models_dir / f"seed_{seed}" / field_name
        if seed_field_dir.is_dir():
            for child in sorted(seed_field_dir.glob("epoch_*")):
                if child.is_dir():
                    candidates.insert(0, child)

        matched: Path | None = None
        for cand in candidates:
            if not cand.is_dir():
                continue
            has_config = (cand / "config.json").is_file()
            has_weights = (
                (cand / "model.safetensors").is_file()
                or (cand / "pytorch_model.bin").is_file()
                or (cand / "model_int8.onnx").is_file()
                or (cand / "model.onnx").is_file()
            )
            if has_config and has_weights:
                matched = cand
                break
        if matched is None:
            return None
        found[field_name] = matched
    return found


def compute_checkpoint_fingerprint(checkpoint_dirs: dict[str, Path]) -> str:
    """Short deterministic SHA-256 provenance fingerprint across the 4 model weight files."""
    hasher = hashlib.sha256()
    for field_name in CLASSIFICATION_FIELDS:
        cdir = checkpoint_dirs[field_name]
        wfile = next(
            (
                cdir / fname
                for fname in ("model.safetensors", "pytorch_model.bin", "model_int8.onnx", "model.onnx")
                if (cdir / fname).is_file()
            ),
            cdir / "model.safetensors",
        )
        hasher.update(field_name.encode("utf-8"))
        with wfile.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
    return hasher.hexdigest()[:12]


def validate_and_score_raw_outputs(
    raw_outputs: dict[str, dict],
    *,
    confidence_threshold: float,
    model_version: str,
) -> ClassificationResult:
    """Validate raw per-field model outputs against fixed taxonomy and probability rules (FR6-FR8, AI3).

    Expected raw_outputs shape per field:
      {field: {"label": str | None, "probabilities": {class_name: float}}}
    """
    labels: dict[str, str | None] = {}
    probabilities: dict[str, dict[str, float]] = {}
    rejected_labels: dict[str, str] = {}
    label_sources: dict[str, str] = {}
    top_probs: list[float] = []
    review_reasons: list[str] = []

    for field_name in CLASSIFICATION_FIELDS:
        allowed = ALLOWED_CLASSES_BY_FIELD[field_name]
        trained = TRAINED_CLASSES_BY_FIELD[field_name]
        field_out = raw_outputs.get(field_name)
        if not isinstance(field_out, dict):
            labels[field_name] = None
            probabilities[field_name] = {}
            label_sources[field_name] = "model"
            review_reasons.append("missing_label")
            continue

        raw_probs = field_out.get("probabilities")
        clean_probs: dict[str, float] = {}
        probs_valid = isinstance(raw_probs, dict) and set(raw_probs.keys()) == set(trained)
        if probs_valid:
            for cls_name in trained:
                val = raw_probs[cls_name]
                if (
                    isinstance(val, bool)
                    or not isinstance(val, (int, float))
                    or not math.isfinite(val)
                    or val < 0.0
                    or val > 1.0
                ):
                    probs_valid = False
                    break
                clean_probs[cls_name] = float(val)
            if probs_valid and abs(sum(clean_probs.values()) - 1.0) > PROB_SUM_TOLERANCE:
                probs_valid = False

        raw_label = field_out.get("label")
        if raw_label is None:
            labels[field_name] = None
            probabilities[field_name] = clean_probs if probs_valid else {}
            label_sources[field_name] = "model"
            review_reasons.append("missing_label")
            continue

        if not isinstance(raw_label, str) or raw_label not in allowed:
            rejected_labels[field_name] = str(raw_label)
            labels[field_name] = None
            probabilities[field_name] = clean_probs if probs_valid else {}
            label_sources[field_name] = "model"
            review_reasons.append("invalid_label")
            continue

        if not probs_valid:
            labels[field_name] = None
            probabilities[field_name] = {}
            label_sources[field_name] = "model"
            review_reasons.append("invalid_label")
            continue

        labels[field_name] = raw_label
        probabilities[field_name] = clean_probs
        label_sources[field_name] = "model"
        top_probs.append(clean_probs.get(raw_label, 0.0))

    if len(top_probs) == len(CLASSIFICATION_FIELDS):
        confidence = round(min(top_probs), 6)
    else:
        confidence = 0.0

    needs_review = False
    primary_reason: str | None = None
    if "invalid_label" in review_reasons:
        needs_review = True
        primary_reason = "invalid_label"
    elif "missing_label" in review_reasons:
        needs_review = True
        primary_reason = "missing_label"
    elif confidence < confidence_threshold:
        needs_review = True
        primary_reason = "low_confidence"

    return ClassificationResult(
        labels=labels,
        probabilities=probabilities,
        confidence=confidence,
        needs_human_review=needs_review,
        review_reason=primary_reason,
        model_version=model_version,
        rejected_labels=rejected_labels,
        label_sources=label_sources,
        error="",
    )


class ValidatedPredictionsIndex:
    """Optional read-only index of the repo's validated MARBERTv2 validation-set predictions.

    Loads ONLY clean_training_val.csv + runs/exp_fair-marbertv2-lr2e5/predictions_val_seed42.json
    (NEVER the frozen test split). Used when local MARBERTv2 Drive checkpoints are not mounted
    so validation corpus voicemails can still exercise genuine MARBERTv2 single-task probabilities.
    """

    def __init__(self, repo_root: Path, seed: int = 42) -> None:
        self.repo_root = repo_root
        self.seed = seed
        self._by_text_norm: dict[str, dict] = {}
        self._by_file: dict[str, dict] = {}
        self.model_version = f"UBC-NLP/MARBERTv2:fair-marbertv2-lr2e5-seed{seed}-validated-artifact"
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        val_csv = self.repo_root / "final" / "clean_training_val.csv"
        pred_json = (
            self.repo_root
            / "runs"
            / "exp_fair-marbertv2-lr2e5"
            / f"predictions_val_seed{self.seed}.json"
        )
        if not val_csv.is_file() or not pred_json.is_file():
            logger.info("Validated MARBERTv2 prediction artifacts not present under %s", self.repo_root)
            return

        pred_payload = json.loads(pred_json.read_text(encoding="utf-8"))
        preds_by_audio = {row["audio_file"]: row for row in pred_payload.get("rows", [])}
        with val_csv.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                af = row["audio_file"]
                pred = preds_by_audio.get(af)
                if pred is None:
                    continue
                formatted = {
                    field_name: {
                        "label": pred["labels"][field_name],
                        "probabilities": pred["probabilities"][field_name],
                    }
                    for field_name in CLASSIFICATION_FIELDS
                }
                self._by_file[af] = formatted
                tn = row.get("text_norm", "").strip()
                if tn:
                    self._by_text_norm[tn] = formatted

    def lookup(self, text_norm: str, file_name: str = "") -> dict[str, dict] | None:
        self._load()
        if text_norm and text_norm in self._by_text_norm:
            return self._by_text_norm[text_norm]
        base = Path(file_name).name if file_name else ""
        if base and base in self._by_file:
            return self._by_file[base]
        return None


class MARBERTv2ClassifierService:
    """Self-hosted single-task MARBERTv2 classifier (4 independent models, one per field)."""

    def __init__(
        self,
        *,
        models_dir: Path,
        repo_root: Path | None = None,
        base_model_id: str = "UBC-NLP/MARBERTv2",
        seed: int = 42,
        max_retries: int = 3,
        retry_backoff_s: float = 0.25,
        allow_validated_artifact_fallback: bool = True,
        low_memory_mode: bool | None = None,
        predictor_override: Callable[[str], dict[str, dict]] | None = None,
    ) -> None:
        self.models_dir = Path(models_dir)
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
        self.base_model_id = base_model_id
        self.seed = seed
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        self.allow_validated_artifact_fallback = allow_validated_artifact_fallback
        self._low_memory_override = low_memory_mode
        self._predictor_override = predictor_override
        self._lock = threading.Lock()
        self._models: dict[str, object] | None = None
        self._ckpt_dirs: dict[str, Path] | None = None
        self._tokenizer = None
        self._device = "cpu"
        self._loaded_model_version: str | None = None
        self._validated_index = ValidatedPredictionsIndex(self.repo_root, seed=seed)

    def _is_low_memory(self, device: str) -> bool:
        if self._low_memory_override is not None:
            return bool(self._low_memory_override)
        env_flag = os.environ.get("SVR_LOW_MEMORY_MODE", "").strip().lower()
        if env_flag in ("1", "true", "yes"):
            return True
        if env_flag in ("0", "false", "no"):
            return False
        return device == "cpu"

    @staticmethod
    def _onnx_path_for(ckpt_dir: Path) -> Path | None:
        for fname in ("model_int8.onnx", "model.onnx"):
            candidate = ckpt_dir / fname
            if candidate.is_file():
                return candidate
        return None

    def _use_onnx_backend(self, ckpt_dirs: dict[str, Path]) -> bool:
        backend = os.environ.get("SVR_MARBERT_BACKEND", "auto").strip().lower()
        if backend == "torch":
            return False
        if self._device != "cpu" and backend != "onnx":
            return False
        if not all(self._onnx_path_for(ckpt_dirs[f]) is not None for f in CLASSIFICATION_FIELDS):
            return False
        try:
            import onnxruntime  # noqa: F401
            return True
        except ImportError:
            return False

    def has_local_checkpoints(self) -> bool:
        return discover_single_task_checkpoints(self.models_dir, seed=self.seed) is not None

    def _ensure_tokenizer_and_metadata(self) -> dict[str, Path]:
        if self._tokenizer is not None and self._ckpt_dirs is not None and self._loaded_model_version is not None:
            return self._ckpt_dirs
        with self._lock:
            if self._tokenizer is not None and self._ckpt_dirs is not None and self._loaded_model_version is not None:
                return self._ckpt_dirs
            ckpt_dirs = discover_single_task_checkpoints(self.models_dir, seed=self.seed)
            if ckpt_dirs is None:
                raise RuntimeError(
                    f"MARBERTv2 single-task checkpoints not found under {self.models_dir}"
                )
            import torch
            from transformers import AutoTokenizer

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            first_dir = ckpt_dirs[CLASSIFICATION_FIELDS[0]]
            tok_dir = first_dir if (first_dir / "tokenizer_config.json").is_file() else self.base_model_id
            self._tokenizer = AutoTokenizer.from_pretrained(str(tok_dir))
            fp = compute_checkpoint_fingerprint(ckpt_dirs)
            self._loaded_model_version = f"{self.base_model_id}:single-task-lr2e5-sha{fp}"
            self._ckpt_dirs = ckpt_dirs
            return ckpt_dirs

    def _load_checkpoints(self) -> None:
        if self._models is not None:
            return
        ckpt_dirs = self._ensure_tokenizer_and_metadata()
        with self._lock:
            if self._models is not None:
                return
            from transformers import AutoModelForSequenceClassification

            loaded: dict[str, object] = {}
            for field_name in CLASSIFICATION_FIELDS:
                model = AutoModelForSequenceClassification.from_pretrained(str(ckpt_dirs[field_name]))
                model.to(self._device)
                model.eval()
                loaded[field_name] = model

            self._models = loaded
            logger.info("Loaded 4 single-task MARBERTv2 checkpoints (%s) on %s", self._loaded_model_version, self._device)

    @staticmethod
    def _score_single_model(model: object, enc: dict, field_name: str) -> dict:
        import torch

        with torch.no_grad():
            logits = model(**enc).logits[0]
            probs_tensor = torch.softmax(logits.float(), dim=-1).cpu().tolist()
        id2label = getattr(model.config, "id2label", None) or {}
        classes = TRAINED_CLASSES_BY_FIELD[field_name]
        if id2label and set(str(v) for v in id2label.values()) == set(classes):
            prob_map = {str(id2label[i]): float(probs_tensor[i]) for i in range(len(probs_tensor))}
        else:
            prob_map = {classes[i]: float(probs_tensor[i]) for i in range(len(classes))}
        total = sum(prob_map.values())
        if total > 0:
            prob_map = {k: v / total for k, v in prob_map.items()}
        best_label = max(classes, key=lambda c: prob_map[c])
        return {"label": best_label, "probabilities": prob_map}

    @staticmethod
    def _logits_to_prediction(logits_row: list[float], id2label: dict, field_name: str) -> dict:
        max_logit = max(logits_row)
        exps = [math.exp(x - max_logit) for x in logits_row]
        exp_sum = sum(exps) or 1.0
        probs_list = [e / exp_sum for e in exps]
        classes = TRAINED_CLASSES_BY_FIELD[field_name]
        if id2label and set(str(v) for v in id2label.values()) == set(classes):
            prob_map = {str(id2label[i]): float(probs_list[i]) for i in range(len(probs_list))}
        else:
            prob_map = {classes[i]: float(probs_list[i]) for i in range(len(classes))}
        total = sum(prob_map.values())
        if total > 0:
            prob_map = {k: v / total for k, v in prob_map.items()}
        best_label = max(classes, key=lambda c: prob_map[c])
        return {"label": best_label, "probabilities": prob_map}

    @classmethod
    def _score_single_onnx(cls, session: object, enc_np: dict, id2label: dict, field_name: str) -> dict:
        input_names = {inp.name for inp in session.get_inputs()}  # type: ignore[attr-defined]
        feed = {k: v for k, v in enc_np.items() if k in input_names}
        logits = session.run(["logits"], feed)[0][0]  # type: ignore[attr-defined]
        return cls._logits_to_prediction([float(x) for x in logits], id2label, field_name)

    def _predict_with_onnx(self, ckpt_dirs: dict[str, Path], text_norm: str) -> tuple[dict[str, dict], str]:
        import onnxruntime as ort

        assert self._tokenizer is not None
        enc_np = self._tokenizer(
            text_norm,
            truncation=True,
            max_length=MAX_SEQ_LEN,
            padding=True,
            return_tensors="np",
        )
        outputs: dict[str, dict] = {}
        low_mem = self._is_low_memory(self._device)
        if not low_mem and self._models is None:
            with self._lock:
                if self._models is None:
                    sessions: dict[str, object] = {}
                    for field_name in CLASSIFICATION_FIELDS:
                        onnx_path = self._onnx_path_for(ckpt_dirs[field_name])
                        assert onnx_path is not None
                        cfg = json.loads((ckpt_dirs[field_name] / "config.json").read_text(encoding="utf-8"))
                        id2label = {int(k): v for k, v in (cfg.get("id2label") or {}).items()}
                        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                        sessions[field_name] = (sess, id2label)
                    self._models = sessions

        if not low_mem and self._models is not None:
            for field_name in CLASSIFICATION_FIELDS:
                sess, id2label = self._models[field_name]  # type: ignore[misc]
                outputs[field_name] = self._score_single_onnx(sess, enc_np, id2label, field_name)
            return outputs, self._loaded_model_version or f"{self.base_model_id}:single-task-lr2e5-onnx"

        with self._lock:
            for field_name in CLASSIFICATION_FIELDS:
                onnx_path = self._onnx_path_for(ckpt_dirs[field_name])
                assert onnx_path is not None
                cfg = json.loads((ckpt_dirs[field_name] / "config.json").read_text(encoding="utf-8"))
                id2label = {int(k): v for k, v in (cfg.get("id2label") or {}).items()}
                sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                try:
                    outputs[field_name] = self._score_single_onnx(sess, enc_np, id2label, field_name)
                finally:
                    del sess
                    gc.collect()
        return outputs, self._loaded_model_version or f"{self.base_model_id}:single-task-lr2e5-onnx"

    def _predict_with_checkpoints(self, text_norm: str) -> tuple[dict[str, dict], str]:
        ckpt_dirs = self._ensure_tokenizer_and_metadata()
        if self._use_onnx_backend(ckpt_dirs):
            return self._predict_with_onnx(ckpt_dirs, text_norm)
        assert self._tokenizer is not None
        enc = self._tokenizer(
            text_norm,
            truncation=True,
            max_length=MAX_SEQ_LEN,
            padding=True,
            return_tensors="pt",
        )
        enc = {k: v.to(self._device) for k, v in enc.items()}

        outputs: dict[str, dict] = {}
        if self._is_low_memory(self._device):
            from transformers import AutoModelForSequenceClassification

            with self._lock:
                for field_name in CLASSIFICATION_FIELDS:
                    model = AutoModelForSequenceClassification.from_pretrained(str(ckpt_dirs[field_name]))
                    try:
                        model.to(self._device)
                        model.eval()
                        outputs[field_name] = self._score_single_model(model, enc, field_name)
                    finally:
                        del model
                        gc.collect()
            return outputs, self._loaded_model_version or f"{self.base_model_id}:single-task-lr2e5"

        self._load_checkpoints()
        assert self._models is not None
        for field_name in CLASSIFICATION_FIELDS:
            outputs[field_name] = self._score_single_model(self._models[field_name], enc, field_name)
        return outputs, self._loaded_model_version or f"{self.base_model_id}:single-task-lr2e5"

    def classify(
        self,
        text_norm: str,
        *,
        confidence_threshold: float = 0.5,
        file_name: str = "",
    ) -> ClassificationResult:
        """Classify normalized transcript into 4 independent fields with retry & safe fallback."""
        if not text_norm or not text_norm.strip():
            return ClassificationResult(
                labels={f: None for f in CLASSIFICATION_FIELDS},
                probabilities={f: {} for f in CLASSIFICATION_FIELDS},
                confidence=0.0,
                needs_human_review=True,
                review_reason="missing_label",
                model_version=f"{self.base_model_id}:single-task-lr2e5",
                label_sources={f: "model" for f in CLASSIFICATION_FIELDS},
                error="Empty normalized transcript cannot be classified.",
            )

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                if self._predictor_override is not None:
                    raw = self._predictor_override(text_norm)
                    model_ver = f"{self.base_model_id}:single-task-lr2e5-test"
                    return validate_and_score_raw_outputs(
                        raw,
                        confidence_threshold=confidence_threshold,
                        model_version=model_ver,
                    )

                if self.has_local_checkpoints():
                    raw, model_ver = self._predict_with_checkpoints(text_norm)
                    return validate_and_score_raw_outputs(
                        raw,
                        confidence_threshold=confidence_threshold,
                        model_version=model_ver,
                    )

                if self.allow_validated_artifact_fallback:
                    artifact_raw = self._validated_index.lookup(text_norm, file_name=file_name)
                    if artifact_raw is not None:
                        return validate_and_score_raw_outputs(
                            artifact_raw,
                            confidence_threshold=confidence_threshold,
                            model_version=self._validated_index.model_version,
                        )

                raise RuntimeError(
                    f"MARBERTv2 checkpoints not mounted at {self.models_dir} and transcript not in validation artifacts."
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Classification attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    last_error,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_s * attempt)

        # AI1 & NFR14: degrade cleanly to Human Review, never guess or fail silently
        return ClassificationResult(
            labels={f: None for f in CLASSIFICATION_FIELDS},
            probabilities={f: {} for f in CLASSIFICATION_FIELDS},
            confidence=0.0,
            needs_human_review=True,
            review_reason="processing_error",
            model_version=f"{self.base_model_id}:unavailable",
            label_sources={f: "model" for f in CLASSIFICATION_FIELDS},
            error=f"Classification unavailable after {self.max_retries} attempts: {last_error}",
        )
