"""VoiceGate Context Engineering Layer: compacted working memory & JIT retrieval assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Agent, SkillMapping
from .classification import CLASSIFICATION_FIELDS, ClassificationResult
from .memory import AgentMemoryService, EpisodicRetrievalResult


@dataclass
class AdjudicationContext:
    """Compact bounded working memory passed to the Classification Adjudicator."""

    transcript: str
    text_norm: str
    gate_status: str
    gate_confidence: float
    gate_correction_applied: bool
    flagged_fields: list[str]
    trigger_reasons: list[str]
    marbert_top2: dict[str, list[dict[str, Any]]]
    episodic_examples: list[dict[str, Any]]
    knn_votes: dict[str, dict[str, float]]
    max_episode_similarity: float
    semantic_rules: list[str]
    procedural_lessons: list[str]
    routing_skills_context: list[str] = field(default_factory=list)

    def render_compact_prompt_payload(self) -> dict[str, Any]:
        """Serialize strictly compacted context (< ~900 tokens) preventing context rot."""
        return {
            "voicemail_transcript": f"<untrusted_transcript>{self.transcript[:450]}</untrusted_transcript>",
            "normalized_text": f"<untrusted_transcript>{self.text_norm[:450]}</untrusted_transcript>",
            "voicegate_transcript_status": {
                "status": self.gate_status,
                "confidence": round(self.gate_confidence, 3),
                "correction_applied": self.gate_correction_applied,
            },
            "flagged_fields_to_review": self.flagged_fields,
            "trigger_reasons": self.trigger_reasons[:6],
            "marbert_top2_predictions": self.marbert_top2,
            "similar_past_cases_episodic_memory": self.episodic_examples[:4],
            "knn_weighted_label_votes": {
                f: dict(list((self.knn_votes.get(f) or {}).items())[:3])
                for f in CLASSIFICATION_FIELDS
                if self.knn_votes.get(f)
            },
            "domain_taxonomy_rules_semantic_memory": self.semantic_rules[:5],
            "learned_lessons_procedural_memory": self.procedural_lessons[:4],
            "active_routing_teams": self.routing_skills_context[:6],
        }


class ContextAssembler:
    """Implements JIT retrieval + compaction across Memory Layers 2-4 and live routing topology."""

    def assemble(
        self,
        db: Session,
        *,
        organization_id: str,
        transcript: str,
        text_norm: str,
        marbert_result: ClassificationResult,
        gate_status: str,
        gate_confidence: float,
        gate_correction_applied: bool,
        flagged_fields: list[str],
        trigger_reasons: list[str],
        episodic_res: EpisodicRetrievalResult,
        memory_service: AgentMemoryService | None,
    ) -> AdjudicationContext:
        # Summarize MARBERTv2 top-2 probabilities per field
        marbert_top2: dict[str, list[dict[str, Any]]] = {}
        candidate_categories: set[str] = set()
        for field_name in CLASSIFICATION_FIELDS:
            probs = marbert_result.probabilities.get(field_name) or {}
            ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:2]
            marbert_top2[field_name] = [
                {"label": lbl, "prob": round(float(prob), 4)} for lbl, prob in ranked
            ]
            if field_name == "complaint_category":
                for lbl, _ in ranked:
                    candidate_categories.add(lbl)

        for lbl in list((episodic_res.knn_votes.get("complaint_category") or {}).keys())[:2]:
            candidate_categories.add(lbl)

        # Compact episodic examples
        compact_episodes: list[dict[str, Any]] = []
        for ep in episodic_res.episodes[:4]:
            compact_episodes.append(
                {
                    "sim": ep.similarity,
                    "source": ep.source,
                    "text": ep.text_snippet[:110],
                    "labels": ep.final_labels,
                }
            )

        sem_rules: list[str] = []
        proc_rules: list[str] = []
        if memory_service is not None and memory_service.enabled:
            sem_entries = memory_service.retrieve_semantic_entries(
                db, organization_id, candidate_categories, limit=5
            )
            sem_rules = [f"[{e.key}] {e.content}" for e in sem_entries]
            proc_entries = memory_service.retrieve_procedural_rules(
                db, organization_id, candidate_categories, text_norm, limit=4
            )
            proc_rules = [
                f"[{r.trigger_pattern} x{r.support_count}] {r.instruction}" for r in proc_entries
            ]

        # Live routing topology snapshot (specialist availability + capacity)
        mappings = db.scalars(
            select(SkillMapping).where(SkillMapping.organization_id == organization_id)
        ).all()
        skill_by_cat = {m.category: m.skill_name for m in mappings}
        agents = db.scalars(
            select(Agent)
            .where(Agent.organization_id == organization_id, Agent.active.is_(True))
            .order_by(Agent.seed_order.asc())
        ).all()
        routing_ctx = [
            (
                f"{a.name}: skills={a.skills}, available={a.available}, "
                f"load={a.current_load}/{a.capacity}"
            )
            for a in agents[:4]
        ]
        for cat in sorted(candidate_categories)[:3]:
            if cat in skill_by_cat:
                routing_ctx.append(f"category '{cat}' -> skill '{skill_by_cat[cat]}'")

        return AdjudicationContext(
            transcript=transcript,
            text_norm=text_norm,
            gate_status=gate_status,
            gate_confidence=gate_confidence,
            gate_correction_applied=gate_correction_applied,
            flagged_fields=flagged_fields,
            trigger_reasons=trigger_reasons,
            marbert_top2=marbert_top2,
            episodic_examples=compact_episodes,
            knn_votes=episodic_res.knn_votes,
            max_episode_similarity=episodic_res.max_similarity,
            semantic_rules=sem_rules,
            procedural_lessons=proc_rules,
            routing_skills_context=routing_ctx,
        )
