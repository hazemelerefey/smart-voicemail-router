"""Shared runtime factories for STT and VoiceGate across API and standalone workers."""

from __future__ import annotations

import logging

from ..config import Settings
from .adjudicator import ClassificationAdjudicator
from .agentic_gate import AgenticTranscriptGate
from .context_layer import ContextAssembler
from .memory import AgentMemoryService, LocalEmbeddingClient
from .stt import BaseSTTService, CohereArabicSTTService, WhisperSTTService
from .transcript_gate import TranscriptVerificationGate

logger = logging.getLogger("svr_platform.factories")


def build_stt_service(settings: Settings) -> BaseSTTService:
    """Construct the configured local STT backend from Settings."""
    backend = (settings.stt_backend or "faster_whisper").strip().lower()
    whisper_cache = str(settings.repo_root / ".cache" / "huggingface")

    if backend == "auto":
        try:
            import torch

            if torch.cuda.is_available():
                backend = "cohere_gpu_int8"
            else:
                backend = "faster_whisper"
        except ImportError:
            backend = "faster_whisper"

    if backend == "cohere_gpu_int8":
        return CohereArabicSTTService(
            backend_mode="cohere_gpu_int8",
            model_id=settings.cohere_model_id,
            device="cuda",
            compute_type="int8",
            local_files_only=settings.cohere_local_files_only,
            ffmpeg_bin=settings.ffmpeg_bin,
        )
    if backend == "cohere_bf16":
        return CohereArabicSTTService(
            backend_mode="cohere_bf16",
            model_id=settings.cohere_bf16_model_id,
            device="cuda",
            compute_type="bfloat16",
            local_files_only=settings.cohere_local_files_only,
            ffmpeg_bin=settings.ffmpeg_bin,
        )
    if backend == "cohere_gguf":
        return CohereArabicSTTService(
            backend_mode="cohere_gguf",
            model_id=settings.cohere_gguf_model_path or "cohere-transcribe-arabic-gguf",
            device="cpu",
            compute_type="gguf",
            gguf_bin=settings.cohere_gguf_bin,
            gguf_model_path=settings.cohere_gguf_model_path,
            ffmpeg_bin=settings.ffmpeg_bin,
        )

    return WhisperSTTService(
        model_id=settings.whisper_model_id,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        download_root=whisper_cache,
        ffmpeg_bin=settings.ffmpeg_bin,
    )


def build_transcript_gate(settings: Settings) -> AgenticTranscriptGate | TranscriptVerificationGate:
    """Construct the active VoiceGate transcript verification service from Settings."""
    if settings.agentic_gate_enabled:
        return AgenticTranscriptGate(
            ollama_url=settings.ollama_url,
            ollama_model=settings.qwen_model_id,
            max_iterations=settings.agentic_gate_max_iterations,
            confidence_threshold=settings.qwen_confidence_threshold,
            early_stop_confidence=settings.agentic_gate_early_stop_confidence,
            timeout_s=settings.qwen_timeout_s,
            fast_path_enabled=settings.agentic_gate_fast_path_enabled,
        )
    return TranscriptVerificationGate(
        backend=settings.qwen_backend,
        ollama_url=settings.ollama_url,
        ollama_model=settings.qwen_model_id,
        hf_model_id=settings.qwen_hf_model_id,
        max_rounds=settings.qwen_max_rounds,
        confidence_threshold=settings.qwen_confidence_threshold,
        timeout_s=settings.qwen_timeout_s,
    )


def build_memory_service(settings: Settings) -> AgentMemoryService:
    """Construct the 4-layer VoiceGate cognitive memory service from Settings."""
    is_test = settings.svr_env.lower() == "test"
    embed_client = LocalEmbeddingClient(
        ollama_url=settings.ollama_url,
        embed_model=settings.ollama_embed_model,
        use_ollama=not is_test,
        low_memory_mode=True,
    )
    return AgentMemoryService(
        embed_client=embed_client,
        enabled=bool(settings.memory_enabled),
    )


def build_adjudicator(
    settings: Settings,
    memory_service: AgentMemoryService | None = None,
) -> ClassificationAdjudicator:
    """Construct the VoiceGate Classification Adjudicator from Settings."""
    is_test = settings.svr_env.lower() == "test"
    mem = memory_service or build_memory_service(settings)
    return ClassificationAdjudicator(
        memory_service=mem,
        context_assembler=ContextAssembler(),
        ollama_url=settings.ollama_url,
        ollama_model=settings.qwen_model_id,
        conf_trigger=settings.adjudicator_conf_trigger,
        margin_trigger=settings.adjudicator_margin_trigger,
        knn_k=settings.adjudicator_knn_k,
        timeout_s=settings.qwen_timeout_s,
        low_memory_mode=True,
        enabled=bool(settings.adjudicator_enabled and not is_test),
    )
