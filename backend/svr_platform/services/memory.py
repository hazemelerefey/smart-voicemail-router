"""VoiceGate 4-Layer Cognitive Memory & Self-Training Curator (CoALA / LangMem / Reflexion).

Memory layers implemented:
1. Working Memory   - managed by ContextAssembler per ticket invocation.
2. Episodic Memory  - MemoryEpisode table with bge-m3 embeddings & weighted kNN retrieval.
3. Semantic Memory  - MemorySemanticEntry table with telecom taxonomy boundaries & dialect cues.
4. Procedural Memory- MemoryProceduralRule table storing Reflexion lessons from corrections.

Plus TrainingFeedbackSample curator recording gold/silver/bronze samples for continual training.
Zero data leakage: train-only seeding enforces strict rejection of test/validation splits.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import math
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    MemoryEpisode,
    MemoryProceduralRule,
    MemorySemanticEntry,
    TrainingFeedbackSample,
)
from .classification import CLASSIFICATION_FIELDS
from .text_norm import normalize_transcript
from .transcript_gate import validate_loopback_url

logger = logging.getLogger("svr_platform.memory")

_HASH_EMBED_DIM = 256

# Curated Semantic Memory boundaries targeting known inter-class confusions
DEFAULT_SEMANTIC_ENTRIES: list[dict[str, Any]] = [
    {
        "entry_type": "taxonomy_boundary",
        "key": "cat_balance_vs_billing",
        "related_categories": ["balance_and_data", "billing_and_charges"],
        "confidence": 0.94,
        "content": (
            "balance_and_data: prepaid recharge card credit ('شحنت كارت', 'رصيد', 'جيجات', 'ميجابايت', 'باقة النت خلصت'), "
            "unexpected prepaid balance drain or data quota disappearance. "
            "billing_and_charges: postpaid monthly invoice ('الفاتورة الشهرية', 'كشف حساب', 'ضريبة', 'مديونية', 'دفع بالكارت مرتين'), "
            "incorrect monthly bill amounts, duplicate payment charges, or billed add-on fees."
        ),
    },
    {
        "entry_type": "taxonomy_boundary",
        "key": "cat_sim_vs_cancel",
        "related_categories": ["sim_services", "cancellation_request"],
        "confidence": 0.95,
        "content": (
            "sim_services: SIM swap/replacement ('شريحة بدل فاقد'), damaged/lost SIM suspension to replace ('موبايلي اتسرق وعايز اوقف الشريحة واطلع بدل فاقد'), "
            "SIM activation, PUK, PIN, or eSIM QR provisioning ('eSIM', 'شريحة الكترونية'). "
            "cancellation_request: permanent line termination, contract cancellation, porting out to competitor "
            "('هلغي الخط خالص', 'هسيب الشركة', 'تحويل لشبكة تانية', 'ايقاف الخدمة نهائي')."
        ),
    },
    {
        "entry_type": "taxonomy_boundary",
        "key": "cat_wait_vs_branch_vs_other",
        "related_categories": ["no_reply_or_long_wait", "branch_and_staff", "other"],
        "confidence": 0.93,
        "content": (
            "no_reply_or_long_wait: long hold wait on phone ('مستني على الخط', 'بقالي ساعة محدش بيرد'), unreturned complaint callback ('عملت شكوى ومحدش كلمني'), "
            "or call-center transfer loops with no resolution. "
            "branch_and_staff: physical retail branch visit experience, queue speed, branch closures, or staff/agent behavior ('في الفرع', 'الموظف اتعامل باسلوب وحش'). "
            "other: general inquiries outside active faults (roaming availability, branch opening hours, ownership transfer paperwork)."
        ),
    },
    {
        "entry_type": "taxonomy_boundary",
        "key": "cat_offers_vs_billing",
        "related_categories": ["offers_and_packages", "billing_and_charges", "balance_and_data"],
        "confidence": 0.92,
        "content": (
            "offers_and_packages: questions or failures around promotional offers, rate plan upgrades, bundle migrations, or promo SMS activation "
            "('عرض الصيف', 'ضعف الباقة', 'ترقية الباقة', 'عروض وباقات'). Use billing_and_charges only if an invoice overcharge is the primary issue."
        ),
    },
    {
        "entry_type": "taxonomy_boundary",
        "key": "cat_app_vs_network",
        "related_categories": ["app_and_account", "network_and_connectivity"],
        "confidence": 0.93,
        "content": (
            "app_and_account: mobile operator app crashes, login failure, password reset, OTP code not received, account portal errors ('ابلكيشن', 'تسجيل دخول', 'OTP'). "
            "network_and_connectivity: cellular signal drops (4G/5G), slow internet speed, home Wi-Fi / ADSL / VDSL router disconnects, or dropped voice calls."
        ),
    },
    {
        "entry_type": "taxonomy_boundary",
        "key": "cat_praise_vs_other",
        "related_categories": ["thanks_or_praise", "other"],
        "confidence": 0.95,
        "content": (
            "thanks_or_praise: explicit gratitude, complimenting speed, technician, or care staff ('الف شكر', 'بشكركم', 'ممتازة', 'متعاون جدا') without an unresolved complaint."
        ),
    },
    {
        "entry_type": "dialect_lexicon",
        "key": "churn_risk_triggers_ar",
        "related_categories": ["*"],
        "confidence": 0.92,
        "content": (
            "churn_risk='at_risk' triggers: explicit threat to leave or switch carriers ('هغير الشركة', 'هسيبكم', 'هحول لفودافون/اورانج', 'هلغي الخط'), "
            "severe trust breach or deception ('تضليل', 'نصب', 'بتستغلوا الناس'), or final ultimatum ('دي اخر مرة', 'لو متحلتش همشي'). "
            "Note: SIM suspension for a stolen phone ('بدل فاقد') or sincere praise ('thanks_or_praise') is NOT at_risk unless threatening carrier switch."
        ),
    },
    {
        "entry_type": "dialect_lexicon",
        "key": "urgency_and_state_cues_ar",
        "related_categories": ["*"],
        "confidence": 0.91,
        "content": (
            "complaint_urgency='high': complete outage during work, stolen phone SIM block, repeated multi-day unresolved complaints, urgent travel outage, major billing surprise. "
            "customer_state='mad': strong anger/profanity/ultimatum ('مستفزة جدا', 'قلة احترام', 'حرامية', 'تضليل'). "
            "'frustrated': annoyed/disappointed ('مش معقول', 'بقالي يومين', 'محدش رد'). 'satisfied': appreciative/happy. 'calm': polite neutral inquiry."
        ),
    },
]

DEFAULT_PROCEDURAL_RULES: list[dict[str, Any]] = [
    {
        "rule_type": "confusion_override",
        "trigger_pattern": "sim_replacement_over_cancel",
        "instruction": (
            "If caller wants to suspend/block a stolen or damaged SIM to issue a replacement ('بدل فاقد', 'eSIM', 'شريحة جديدة'), "
            "classify complaint_category as 'sim_services', NOT 'cancellation_request'."
        ),
        "support_count": 3,
        "success_count": 3,
        "source": "seeded",
    },
    {
        "rule_type": "adjudication_lesson",
        "trigger_pattern": "churn_ultimatum_escalation",
        "instruction": (
            "When a subscriber threatens to leave the company or switch networks ('هغير الشركة', 'هحول رقمي', 'تضليل'), "
            "audit churn_risk carefully even if MARBERT outputs 'not_at_risk' due to class imbalance."
        ),
        "support_count": 5,
        "success_count": 5,
        "source": "seeded",
    },
    {
        "rule_type": "adjudication_lesson",
        "trigger_pattern": "repeated_contact_wait_vs_branch",
        "instruction": (
            "Complaints about long phone wait times, unanswered tickets, or repeated call-center handoffs map to 'no_reply_or_long_wait' "
            "or 'branch_and_staff' depending on whether a physical retail branch ('فرع') vs phone callback/queue is cited; inspect episodic kNN matches closely."
        ),
        "support_count": 4,
        "success_count": 4,
        "source": "seeded",
    },
    {
        "rule_type": "calibration_stat",
        "trigger_pattern": "coherent_asr_reduces_human_review",
        "instruction": (
            "If transcript is coherent Egyptian Arabic (>=4 words, no repetition loop) and episodic kNN + LLM agree on all 4 labels "
            "at >=0.65 calibrated confidence, approve automatic agent routing instead of unnecessary human review."
        ),
        "support_count": 3,
        "success_count": 3,
        "source": "seeded",
    },
]


def compute_lexical_embedding(text: str, dim: int = _HASH_EMBED_DIM) -> list[float]:
    """Deterministic L2-normalized char-trigram + word-unigram hashed vector (offline fallback)."""
    norm = normalize_transcript(text or "")
    vec = np.zeros(dim, dtype=np.float32)
    if not norm:
        return vec.tolist()
    tokens = norm.split()
    features: list[str] = list(tokens)
    padded = f" {norm} "
    for idx in range(max(0, len(padded) - 2)):
        features.append(padded[idx : idx + 3])
    for feat in features:
        h = int(hashlib.blake2b(feat.encode("utf-8"), digest_size=4).hexdigest(), 16)
        bucket = h % dim
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        vec[bucket] += sign
    norm_val = float(np.linalg.norm(vec))
    if norm_val > 1e-8:
        vec /= norm_val
    return [round(float(x), 6) for x in vec.tolist()]


def _cosine_similarity_matrix(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Return cosine similarity between normalized rows of matrix (N, D) and query (D,)."""
    q_norm = float(np.linalg.norm(query))
    if q_norm <= 1e-8 or matrix.size == 0:
        return np.zeros((matrix.shape[0],), dtype=np.float32)
    q_unit = query / q_norm
    return matrix @ q_unit


class LocalEmbeddingClient:
    """Loopback Ollama embedding client (`bge-m3:latest`) with deterministic offline fallback."""

    def __init__(
        self,
        *,
        ollama_url: str = "http://127.0.0.1:11434",
        embed_model: str = "bge-m3:latest",
        use_ollama: bool = True,
        timeout_s: float = 90.0,
        low_memory_mode: bool = True,
    ) -> None:
        self.ollama_url = validate_loopback_url(ollama_url)
        self.embed_model = embed_model
        self.use_ollama = bool(use_ollama)
        self.timeout_s = float(timeout_s)
        self.low_memory_mode = bool(low_memory_mode)
        self._ollama_loaded = False
        self._query_cache: dict[str, list[float]] = {}
        self._cache_lock = threading.Lock()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more strings via local Ollama or deterministic hashed fallback."""
        if not texts:
            return []
        cleaned = [normalize_transcript(t or "") or (t or "").strip() for t in texts]
        if self.use_ollama:
            try:
                out: list[list[float]] = []
                batch_size = 16
                for start in range(0, len(cleaned), batch_size):
                    batch = cleaned[start : start + batch_size]
                    with httpx.Client(timeout=self.timeout_s) as client:
                        resp = client.post(
                            f"{self.ollama_url}/api/embed",
                            json={
                                "model": self.embed_model,
                                "input": batch,
                                "keep_alive": "2m",
                            },
                        )
                        resp.raise_for_status()
                        self._ollama_loaded = True
                        data = resp.json()
                        embs = data.get("embeddings") or []
                        if len(embs) != len(batch):
                            raise RuntimeError(f"Expected {len(batch)} embeddings, got {len(embs)}")
                        for vec in embs:
                            arr = np.asarray(vec, dtype=np.float32)
                            n = float(np.linalg.norm(arr))
                            if n > 1e-8:
                                arr = arr / n
                            out.append([round(float(x), 6) for x in arr.tolist()])
                return out
            except Exception as exc:
                logger.warning("Ollama embed failed (%s); falling back to lexical hashing.", exc)
        return [compute_lexical_embedding(t) for t in cleaned]

    def embed_query(self, text: str) -> list[float]:
        key = normalize_transcript(text or "") or (text or "").strip()
        with self._cache_lock:
            cached = self._query_cache.get(key)
        if cached is not None:
            return cached
        vec = self.embed_texts([key])[0]
        with self._cache_lock:
            if len(self._query_cache) > 512:
                self._query_cache.clear()
            self._query_cache[key] = vec
        return vec

    def unload(self) -> None:
        if not self._ollama_loaded:
            return
        self._ollama_loaded = False
        try:
            with httpx.Client(timeout=3.0) as client:
                client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.embed_model, "prompt": "", "keep_alive": 0},
                )
            logger.info("Unloaded Ollama embedding model=%s via keep_alive=0.", self.embed_model)
        except Exception as exc:
            logger.debug("Optional embed unload skipped: %s", exc)


@dataclass
class RetrievedEpisode:
    id: str
    ticket_id: str | None
    source: str
    similarity: float
    trust_weight: float
    text_snippet: str
    final_labels: dict[str, str]
    marbert_labels: dict[str, str]
    was_corrected: bool
    adjudication_rationale: str


@dataclass
class EpisodicRetrievalResult:
    episodes: list[RetrievedEpisode] = field(default_factory=list)
    knn_votes: dict[str, dict[str, float]] = field(default_factory=dict)
    max_similarity: float = 0.0
    total_episodes_searched: int = 0


def _assert_safe_train_seed_path(csv_path: Path) -> None:
    """Strictly reject any validation or test dataset split from ever entering agent memory."""
    stem_tokens = set(re.split(r"[^a-z0-9]+", csv_path.stem.lower()))
    parent_names = {p.lower() for p in csv_path.parts[:-1]}
    forbidden = {"test", "val", "validation"}
    if (stem_tokens & forbidden) or (parent_names & forbidden):
        raise ValueError(
            f"Leakage guard blocked seeding memory from '{csv_path}': only training splits may seed memory."
        )


def _select_balanced_train_rows(rows: list[dict[str, str]], max_per_category: int) -> list[dict[str, str]]:
    """Select balanced stratified train exemplars preserving all rare at_risk and mad/satisfied cases."""
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    by_cat: dict[str, list[dict[str, str]]] = {}

    for row in rows:
        af = (row.get("audio_file") or row.get("file") or "").strip()
        tn = (row.get("text_norm") or row.get("text") or "").strip()
        cat = (row.get("complaint_category") or "").strip()
        if not af or not tn or not cat:
            continue
        by_cat.setdefault(cat, []).append(row)

    # 1. Include all at_risk churn samples + prioritize mad & high urgency for balanced coverage
    priority_rows = [
        r
        for cat_rows in by_cat.values()
        for r in cat_rows
        if r.get("churn_risk") == "at_risk" or r.get("customer_state") == "mad"
    ]
    cat_counts: dict[str, int] = {}
    for row in priority_rows:
        af = (row.get("audio_file") or row.get("file") or "").strip()
        cat = row["complaint_category"].strip()
        if af in seen:
            continue
        if row.get("churn_risk") != "at_risk" and cat_counts.get(cat, 0) >= max(4, max_per_category // 4):
            continue
        seen.add(af)
        selected.append(row)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # 2. Fill each category up to max_per_category
    for cat, cat_rows in sorted(by_cat.items()):
        for row in cat_rows:
            if cat_counts.get(cat, 0) >= max_per_category:
                break
            af = (row.get("audio_file") or row.get("file") or "").strip()
            if af in seen:
                continue
            seen.add(af)
            selected.append(row)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    return selected


class AgentMemoryService:
    """Coordinated 4-layer memory & self-training curator persisted in SQLAlchemy."""

    def __init__(
        self,
        *,
        embed_client: LocalEmbeddingClient | None = None,
        enabled: bool = True,
    ) -> None:
        self.embed_client = embed_client or LocalEmbeddingClient(use_ollama=False)
        self.enabled = bool(enabled)
        self._matrix_lock = threading.Lock()
        self._matrix_cache: dict[str, tuple[int, np.ndarray, list[dict[str, Any]]]] = {}

    def invalidate_cache(self, organization_id: str | None = None) -> None:
        with self._matrix_lock:
            if organization_id is None:
                self._matrix_cache.clear()
            else:
                self._matrix_cache.pop(organization_id, None)

    def ensure_default_semantic_and_procedural_memory(self, db: Session, organization_id: str) -> None:
        """Idempotently seed Layer 3 Semantic & initial Layer 4 Procedural rules for an org."""
        if not self.enabled:
            return
        added = False
        for item in DEFAULT_SEMANTIC_ENTRIES:
            exists = db.scalar(
                select(MemorySemanticEntry).where(
                    MemorySemanticEntry.organization_id == organization_id,
                    MemorySemanticEntry.key == item["key"],
                )
            )
            if exists is None:
                db.add(
                    MemorySemanticEntry(
                        organization_id=organization_id,
                        entry_type=item["entry_type"],
                        key=item["key"],
                        content=item["content"],
                        related_categories=list(item["related_categories"]),
                        confidence=float(item["confidence"]),
                        hit_count=0,
                    )
                )
                added = True

        for rule in DEFAULT_PROCEDURAL_RULES:
            exists_r = db.scalar(
                select(MemoryProceduralRule).where(
                    MemoryProceduralRule.organization_id == organization_id,
                    MemoryProceduralRule.trigger_pattern == rule["trigger_pattern"],
                )
            )
            if exists_r is None:
                db.add(
                    MemoryProceduralRule(
                        organization_id=organization_id,
                        rule_type=rule["rule_type"],
                        trigger_pattern=rule["trigger_pattern"],
                        instruction=rule["instruction"],
                        support_count=int(rule["support_count"]),
                        success_count=int(rule["success_count"]),
                        active=True,
                        source=rule["source"],
                    )
                )
                added = True

        if added:
            db.commit()

    def seed_episodic_memory_from_train(
        self,
        db: Session,
        organization_id: str,
        train_csv_path: Path | str,
        *,
        max_per_category: int = 40,
    ) -> int:
        """Seed Layer 2 Episodic Memory strictly from clean_training_train.csv."""
        if not self.enabled:
            return 0
        csv_path = Path(train_csv_path)
        _assert_safe_train_seed_path(csv_path)
        if not csv_path.is_file():
            logger.warning("Train seed CSV not found at %s; skipping episodic seeding.", csv_path)
            return 0

        existing_count = int(
            db.scalar(
                select(func.count(MemoryEpisode.id)).where(
                    MemoryEpisode.organization_id == organization_id,
                    MemoryEpisode.source == "train_seed",
                )
            )
            or 0
        )
        if existing_count > 0:
            return 0

        with csv_path.open("r", encoding="utf-8") as fh:
            raw_rows = list(csv.DictReader(fh))
        chosen = _select_balanced_train_rows(raw_rows, max_per_category=max_per_category)
        if not chosen:
            return 0

        texts_norm = [
            normalize_transcript((r.get("text_norm") or r.get("text") or "").strip())
            for r in chosen
        ]
        embeddings = self.embed_client.embed_texts(texts_norm)

        inserted = 0
        for row, tn, emb in zip(chosen, texts_norm, embeddings):
            if not tn:
                continue
            labels = {
                f: (row.get(f) or "").strip()
                for f in CLASSIFICATION_FIELDS
            }
            if not all(labels.values()):
                continue
            raw_txt = (row.get("text") or tn).strip()
            trust = 1.0
            db.add(
                MemoryEpisode(
                    organization_id=organization_id,
                    ticket_id=None,
                    source="train_seed",
                    trust_weight=trust,
                    transcript=raw_txt,
                    text_norm=tn,
                    embedding_json=emb,
                    marbert_labels=labels,
                    final_labels=labels,
                    adjudication_rationale=f"Verified training exemplar ({row.get('audio_file', '')}).",
                    was_corrected=False,
                    confidence=1.0,
                )
            )
            inserted += 1

        db.commit()
        self.invalidate_cache(organization_id)
        logger.info("Seeded %d episodic memory exemplars for org=%s from train split.", inserted, organization_id)
        return inserted

    def _get_org_matrix(
        self,
        db: Session,
        organization_id: str,
        target_dim: int,
    ) -> tuple[np.ndarray, list[dict[str, Any]]]:
        total_rows = int(
            db.scalar(
                select(func.count(MemoryEpisode.id)).where(
                    MemoryEpisode.organization_id == organization_id
                )
            )
            or 0
        )
        with self._matrix_lock:
            cached = self._matrix_cache.get(organization_id)
            if cached is not None and cached[0] == total_rows and (cached[1].size == 0 or cached[1].shape[1] == target_dim):
                return cached[1], cached[2]

        rows = db.scalars(
            select(MemoryEpisode)
            .where(MemoryEpisode.organization_id == organization_id)
            .order_by(MemoryEpisode.created_at.desc())
        ).all()

        vecs: list[list[float]] = []
        meta: list[dict[str, Any]] = []
        for ep in rows:
            emb = ep.embedding_json
            if isinstance(emb, list) and len(emb) == target_dim:
                vecs.append([float(v) for v in emb])
                meta.append(
                    {
                        "id": ep.id,
                        "ticket_id": ep.ticket_id,
                        "source": ep.source,
                        "trust_weight": float(ep.trust_weight),
                        "transcript": ep.transcript,
                        "text_norm": ep.text_norm,
                        "marbert_labels": dict(ep.marbert_labels or {}),
                        "final_labels": dict(ep.final_labels or {}),
                        "was_corrected": bool(ep.was_corrected),
                        "adjudication_rationale": ep.adjudication_rationale,
                    }
                )
            elif ep.text_norm and target_dim == _HASH_EMBED_DIM:
                vecs.append(compute_lexical_embedding(ep.text_norm, dim=_HASH_EMBED_DIM))
                meta.append(
                    {
                        "id": ep.id,
                        "ticket_id": ep.ticket_id,
                        "source": ep.source,
                        "trust_weight": float(ep.trust_weight),
                        "transcript": ep.transcript,
                        "text_norm": ep.text_norm,
                        "marbert_labels": dict(ep.marbert_labels or {}),
                        "final_labels": dict(ep.final_labels or {}),
                        "was_corrected": bool(ep.was_corrected),
                        "adjudication_rationale": ep.adjudication_rationale,
                    }
                )

        if vecs:
            mat = np.asarray(vecs, dtype=np.float32)
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms = np.where(norms > 1e-8, norms, 1.0)
            mat = mat / norms
        else:
            mat = np.zeros((0, target_dim), dtype=np.float32)

        with self._matrix_lock:
            self._matrix_cache[organization_id] = (total_rows, mat, meta)
        return mat, meta

    def retrieve_similar_episodes(
        self,
        db: Session,
        organization_id: str,
        text_norm: str,
        *,
        top_k: int = 7,
        exclude_ticket_id: str | None = None,
    ) -> EpisodicRetrievalResult:
        """Retrieve top-k similar past episodes and compute weighted class votes per field."""
        if not self.enabled or not (text_norm or "").strip():
            return EpisodicRetrievalResult()

        q_vec = self.embed_client.embed_query(text_norm)
        q_arr = np.asarray(q_vec, dtype=np.float32)
        mat, meta = self._get_org_matrix(db, organization_id, len(q_vec))

        if mat.shape[0] == 0:
            # Fallback to lexical similarity if episodes exist with a different embedding dimension
            all_eps = db.scalars(
                select(MemoryEpisode)
                .where(MemoryEpisode.organization_id == organization_id)
                .order_by(MemoryEpisode.created_at.desc())
            ).all()
            if not all_eps:
                return EpisodicRetrievalResult()
            q_lex = np.asarray(compute_lexical_embedding(text_norm, dim=_HASH_EMBED_DIM), dtype=np.float32)
            lex_vecs = [compute_lexical_embedding(e.text_norm or e.transcript, dim=_HASH_EMBED_DIM) for e in all_eps]
            mat = np.asarray(lex_vecs, dtype=np.float32)
            meta = [
                {
                    "id": e.id,
                    "ticket_id": e.ticket_id,
                    "source": e.source,
                    "trust_weight": float(e.trust_weight),
                    "transcript": e.transcript,
                    "text_norm": e.text_norm,
                    "marbert_labels": dict(e.marbert_labels or {}),
                    "final_labels": dict(e.final_labels or {}),
                    "was_corrected": bool(e.was_corrected),
                    "adjudication_rationale": e.adjudication_rationale,
                }
                for e in all_eps
            ]
            q_arr = q_lex

        sims = _cosine_similarity_matrix(mat, q_arr)
        scored_indices: list[tuple[float, float, int]] = []
        for idx, m in enumerate(meta):
            if exclude_ticket_id and m.get("ticket_id") == exclude_ticket_id:
                continue
            raw_sim = float(sims[idx])
            if raw_sim <= 0.0:
                continue
            weighted = raw_sim * float(m.get("trust_weight", 1.0))
            scored_indices.append((weighted, raw_sim, idx))

        scored_indices.sort(key=lambda item: item[0], reverse=True)
        top_items = scored_indices[: max(1, int(top_k))]

        episodes: list[RetrievedEpisode] = []
        votes: dict[str, dict[str, float]] = {f: {} for f in CLASSIFICATION_FIELDS}
        vote_totals: dict[str, float] = {f: 0.0 for f in CLASSIFICATION_FIELDS}

        for _w_score, raw_sim, idx in top_items:
            m = meta[idx]
            flabels = m.get("final_labels") or {}
            txt = (m.get("transcript") or m.get("text_norm") or "").strip()
            snippet = txt if len(txt) <= 120 else f"{txt[:117]}..."
            episodes.append(
                RetrievedEpisode(
                    id=m["id"],
                    ticket_id=m.get("ticket_id"),
                    source=m["source"],
                    similarity=round(raw_sim, 4),
                    trust_weight=float(m.get("trust_weight", 1.0)),
                    text_snippet=snippet,
                    final_labels=flabels,
                    marbert_labels=m.get("marbert_labels") or {},
                    was_corrected=bool(m.get("was_corrected", False)),
                    adjudication_rationale=m.get("adjudication_rationale", ""),
                )
            )
            contrib = max(raw_sim, 0.0) * float(m.get("trust_weight", 1.0))
            for field_name in CLASSIFICATION_FIELDS:
                lbl = flabels.get(field_name)
                if lbl:
                    votes[field_name][lbl] = votes[field_name].get(lbl, 0.0) + contrib
                    vote_totals[field_name] += contrib

        knn_probs: dict[str, dict[str, float]] = {}
        for field_name in CLASSIFICATION_FIELDS:
            tot = vote_totals[field_name]
            if tot > 0.0:
                knn_probs[field_name] = {
                    lbl: round(val / tot, 4)
                    for lbl, val in sorted(votes[field_name].items(), key=lambda kv: kv[1], reverse=True)
                }
            else:
                knn_probs[field_name] = {}

        max_sim = round(max((e.similarity for e in episodes), default=0.0), 4)
        return EpisodicRetrievalResult(
            episodes=episodes,
            knn_votes=knn_probs,
            max_similarity=max_sim,
            total_episodes_searched=len(meta),
        )

    def retrieve_semantic_entries(
        self,
        db: Session,
        organization_id: str,
        candidate_categories: set[str],
        *,
        limit: int = 5,
    ) -> list[MemorySemanticEntry]:
        """Just-in-time retrieval of semantic boundary rules matching active categories."""
        if not self.enabled:
            return []
        entries = db.scalars(
            select(MemorySemanticEntry)
            .where(MemorySemanticEntry.organization_id == organization_id)
            .order_by(MemorySemanticEntry.confidence.desc())
        ).all()
        matched: list[MemorySemanticEntry] = []
        for entry in entries:
            cats = set(entry.related_categories or [])
            if "*" in cats or not cats or (cats & candidate_categories):
                entry.hit_count += 1
                matched.append(entry)
                if len(matched) >= limit:
                    break
        return matched

    def retrieve_procedural_rules(
        self,
        db: Session,
        organization_id: str,
        candidate_categories: set[str],
        text_norm: str,
        *,
        limit: int = 4,
    ) -> list[MemoryProceduralRule]:
        """Retrieve active Reflexion rules relevant to current classification candidates/text."""
        if not self.enabled:
            return []
        rules = db.scalars(
            select(MemoryProceduralRule)
            .where(
                MemoryProceduralRule.organization_id == organization_id,
                MemoryProceduralRule.active.is_(True),
            )
            .order_by(MemoryProceduralRule.support_count.desc(), MemoryProceduralRule.updated_at.desc())
        ).all()
        chosen: list[MemoryProceduralRule] = []
        fallback: list[MemoryProceduralRule] = []
        low_text = (text_norm or "").lower()
        for rule in rules:
            instr_low = rule.instruction.lower()
            if any(cat in instr_low for cat in candidate_categories) or any(
                tok in low_text for tok in ("شريحة", "فاقد", "هغير", "هلغي", "فرع", "انتظار", "باقة", "فاتور")
            ):
                chosen.append(rule)
            else:
                fallback.append(rule)
        combined = (chosen + fallback)[:limit]
        return combined

    def consolidate_ticket_outcome(
        self,
        db: Session,
        *,
        organization_id: str,
        ticket_id: str,
        transcript: str,
        text_norm: str,
        marbert_labels: dict[str, str | None],
        final_labels: dict[str, str | None],
        confidence: float,
        rationale: str,
        source: str,
        was_corrected: bool,
        learned_lesson: str = "",
        add_to_episodic: bool = True,
    ) -> None:
        """Persist episode (when trusted/high-confidence), training sample, and Reflexion procedural lesson."""
        if not self.enabled or not (text_norm or "").strip():
            return
        if not all(final_labels.get(f) for f in CLASSIFICATION_FIELDS):
            return

        trust_map = {
            "human_correction": 1.5,
            "agent_adjudicated": 1.1,
            "high_conf_verified": 1.0,
            "train_seed": 1.0,
        }
        trust_weight = trust_map.get(source, 1.0)
        tier_map = {
            "human_correction": "gold_human",
            "agent_adjudicated": "silver_agent",
            "high_conf_verified": "bronze_high_conf",
        }
        quality_tier = tier_map.get(source, "bronze_high_conf")
        clean_final = {f: str(final_labels[f]) for f in CLASSIFICATION_FIELDS}
        clean_marbert = {f: str(marbert_labels.get(f) or "") for f in CLASSIFICATION_FIELDS}
        marbert_agreed = all(clean_marbert.get(f) == clean_final.get(f) for f in CLASSIFICATION_FIELDS)

        if add_to_episodic or source == "human_correction":
            emb = self.embed_client.embed_query(text_norm)
            existing_ep = db.scalar(
                select(MemoryEpisode).where(
                    MemoryEpisode.organization_id == organization_id,
                    MemoryEpisode.ticket_id == ticket_id,
                )
            )
            if existing_ep is not None:
                existing_ep.source = source
                existing_ep.trust_weight = trust_weight
                existing_ep.transcript = transcript
                existing_ep.text_norm = text_norm
                existing_ep.embedding_json = emb
                existing_ep.marbert_labels = clean_marbert
                existing_ep.final_labels = clean_final
                existing_ep.adjudication_rationale = rationale[:1000]
                existing_ep.was_corrected = bool(was_corrected)
                existing_ep.confidence = float(confidence)
            else:
                db.add(
                    MemoryEpisode(
                        organization_id=organization_id,
                        ticket_id=ticket_id,
                        source=source,
                        trust_weight=trust_weight,
                        transcript=transcript,
                        text_norm=text_norm,
                        embedding_json=emb,
                        marbert_labels=clean_marbert,
                        final_labels=clean_final,
                        adjudication_rationale=rationale[:1000],
                        was_corrected=bool(was_corrected),
                        confidence=float(confidence),
                    )
                )

        existing_sample = db.scalar(
            select(TrainingFeedbackSample).where(
                TrainingFeedbackSample.organization_id == organization_id,
                TrainingFeedbackSample.ticket_id == ticket_id,
            )
        )
        if existing_sample is not None:
            existing_sample.source = source
            existing_sample.quality_tier = quality_tier
            existing_sample.transcript = transcript
            existing_sample.text_norm = text_norm
            existing_sample.complaint_category = clean_final["complaint_category"]
            existing_sample.complaint_urgency = clean_final["complaint_urgency"]
            existing_sample.customer_state = clean_final["customer_state"]
            existing_sample.churn_risk = clean_final["churn_risk"]
            existing_sample.marbert_agreed = marbert_agreed
            existing_sample.confidence = float(confidence)
        else:
            db.add(
                TrainingFeedbackSample(
                    organization_id=organization_id,
                    ticket_id=ticket_id,
                    source=source,
                    quality_tier=quality_tier,
                    transcript=transcript,
                    text_norm=text_norm,
                    complaint_category=clean_final["complaint_category"],
                    complaint_urgency=clean_final["complaint_urgency"],
                    customer_state=clean_final["customer_state"],
                    churn_risk=clean_final["churn_risk"],
                    marbert_agreed=marbert_agreed,
                    confidence=float(confidence),
                )
            )

        # Reflexion: extract or reinforce a procedural lesson when trusted feedback corrected MARBERT
        if was_corrected and (source == "human_correction" or float(confidence) >= 0.72):
            diffs = [
                f"{f}:{clean_marbert.get(f)}->{clean_final[f]}"
                for f in CLASSIFICATION_FIELDS
                if clean_marbert.get(f) and clean_marbert.get(f) != clean_final[f]
            ]
            trigger = ("|".join(diffs))[:155] if diffs else "adjudicated_calibration"
            lesson_text = (learned_lesson or rationale or "").strip()
            if not lesson_text:
                lesson_text = f"Review pattern {trigger} against episodic examples before accepting model head."
            rule_source = "supervisor_feedback" if source == "human_correction" else "reflection"
            existing_rule = db.scalar(
                select(MemoryProceduralRule).where(
                    MemoryProceduralRule.organization_id == organization_id,
                    MemoryProceduralRule.trigger_pattern == trigger,
                )
            )
            if existing_rule is not None:
                existing_rule.support_count += 1
                existing_rule.success_count += 1
                existing_rule.instruction = lesson_text[:600]
                existing_rule.source = rule_source
                existing_rule.active = True
            else:
                db.add(
                    MemoryProceduralRule(
                        organization_id=organization_id,
                        rule_type="adjudication_lesson",
                        trigger_pattern=trigger,
                        instruction=lesson_text[:600],
                        support_count=1,
                        success_count=1,
                        active=True,
                        source=rule_source,
                    )
                )

        db.flush()
        self.invalidate_cache(organization_id)

    def get_memory_stats(self, db: Session, organization_id: str) -> dict[str, Any]:
        ep_rows = db.execute(
            select(MemoryEpisode.source, func.count(MemoryEpisode.id))
            .where(MemoryEpisode.organization_id == organization_id)
            .group_by(MemoryEpisode.source)
        ).all()
        ep_by_src = {str(s): int(c) for s, c in ep_rows}

        sem_count = int(
            db.scalar(
                select(func.count(MemorySemanticEntry.id)).where(
                    MemorySemanticEntry.organization_id == organization_id
                )
            )
            or 0
        )
        proc_count = int(
            db.scalar(
                select(func.count(MemoryProceduralRule.id)).where(
                    MemoryProceduralRule.organization_id == organization_id,
                    MemoryProceduralRule.active.is_(True),
                )
            )
            or 0
        )
        tf_rows = db.execute(
            select(TrainingFeedbackSample.quality_tier, func.count(TrainingFeedbackSample.id))
            .where(TrainingFeedbackSample.organization_id == organization_id)
            .group_by(TrainingFeedbackSample.quality_tier)
        ).all()
        tf_by_tier = {str(t): int(c) for t, c in tf_rows}

        recent_rules = db.scalars(
            select(MemoryProceduralRule)
            .where(
                MemoryProceduralRule.organization_id == organization_id,
                MemoryProceduralRule.active.is_(True),
            )
            .order_by(MemoryProceduralRule.updated_at.desc())
            .limit(10)
        ).all()

        return {
            "organization_id": organization_id,
            "memory_enabled": self.enabled,
            "embed_model": self.embed_client.embed_model,
            "episodic_total": sum(ep_by_src.values()),
            "episodic_by_source": ep_by_src,
            "semantic_entries_count": sem_count,
            "procedural_rules_active_count": proc_count,
            "training_feedback_total": sum(tf_by_tier.values()),
            "training_feedback_by_tier": tf_by_tier,
            "recent_procedural_lessons": recent_rules,
        }

    def export_training_samples(self, db: Session, organization_id: str) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(TrainingFeedbackSample)
            .where(TrainingFeedbackSample.organization_id == organization_id)
            .order_by(TrainingFeedbackSample.created_at.desc())
        ).all()
        return [
            {
                "id": r.id,
                "ticket_id": r.ticket_id,
                "source": r.source,
                "quality_tier": r.quality_tier,
                "transcript": r.transcript,
                "text_norm": r.text_norm,
                "complaint_category": r.complaint_category,
                "complaint_urgency": r.complaint_urgency,
                "customer_state": r.customer_state,
                "churn_risk": r.churn_risk,
                "marbert_agreed": r.marbert_agreed,
                "confidence": r.confidence,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
