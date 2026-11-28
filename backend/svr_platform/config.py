"""Runtime settings loaded from environment variables (never hardcoded secrets)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_STORAGE = _REPO_ROOT / "storage"
_DEFAULT_MODELS = _REPO_ROOT / "models" / "marbertv2-single-task"


def _default_sqlite_url() -> str:
    db_path = (_DEFAULT_STORAGE / "svr.db").resolve()
    return f"sqlite:///{db_path.as_posix()}"


def _derive_dev_fernet_key(secret: str) -> str:
    digest = hashlib.sha256(f"svr-dev-fernet:{secret}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    svr_env: str = Field(default="development", alias="SVR_ENV")
    svr_org_name: str = Field(default="Egypt Telecom Care", alias="SVR_ORG_NAME")
    svr_org_slug: str = Field(default="egypt-telecom-care", alias="SVR_ORG_SLUG")

    database_url: str = Field(default_factory=_default_sqlite_url, alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")
    redis_queue_key: str = Field(default="svr:pipeline:queue", alias="SVR_REDIS_QUEUE_KEY")
    redis_inflight_key: str = Field(default="svr:pipeline:inflight", alias="SVR_REDIS_INFLIGHT_KEY")
    redis_events_channel: str = Field(default="svr:pipeline:events", alias="SVR_REDIS_EVENTS_CHANNEL")

    svr_secret_key: str = Field(default="", alias="SVR_SECRET_KEY")
    svr_encryption_key: str = Field(default="", alias="SVR_ENCRYPTION_KEY")

    svr_storage_dir: Path = Field(default=_DEFAULT_STORAGE, alias="SVR_STORAGE_DIR")
    svr_models_dir: Path = Field(default=_DEFAULT_MODELS, alias="SVR_MODELS_DIR")

    stt_backend: str = Field(default="faster_whisper", alias="SVR_STT_BACKEND")
    cohere_model_id: str = Field(
        default="NAMAA-Space/cohere-transcribe-arabic-07-2026-int8",
        alias="COHERE_MODEL_ID",
    )
    cohere_bf16_model_id: str = Field(
        default="CohereLabs/cohere-transcribe-arabic-07-2026",
        alias="COHERE_BF16_MODEL_ID",
    )
    cohere_gguf_bin: str = Field(default="", alias="SVR_COHERE_GGUF_BIN")
    cohere_gguf_model_path: str = Field(default="", alias="SVR_COHERE_GGUF_MODEL_PATH")
    cohere_local_files_only: bool = Field(default=True, alias="SVR_COHERE_LOCAL_FILES_ONLY")

    whisper_model_id: str = Field(default="large-v3", alias="WHISPER_MODEL_ID")
    whisper_device: str = Field(default="cpu", alias="WHISPER_DEVICE")
    whisper_compute_type: str = Field(default="int8", alias="WHISPER_COMPUTE_TYPE")
    ollama_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_URL")
    qwen_model_id: str = Field(default="qwen2.5:3b", alias="QWEN_MODEL_ID")
    qwen_hf_model_id: str = Field(default="Qwen/Qwen2.5-0.5B-Instruct", alias="QWEN_HF_MODEL_ID")
    qwen_backend: str = Field(default="auto", alias="QWEN_BACKEND")
    qwen_max_rounds: int = Field(default=4, alias="QWEN_MAX_ROUNDS")
    qwen_confidence_threshold: float = Field(default=0.75, alias="QWEN_CONFIDENCE_THRESHOLD")
    qwen_timeout_s: float = Field(default=60.0, alias="QWEN_TIMEOUT_S")
    # AgenticTranscriptGate settings (LangGraph-powered audit loop)
    transcript_edit_enabled: bool = Field(default=False, alias="SVR_TRANSCRIPT_EDIT_ENABLED")
    agentic_gate_enabled: bool = Field(default=True, alias="AGENTIC_GATE_ENABLED")
    agentic_gate_fast_path_enabled: bool = Field(default=True, alias="AGENTIC_GATE_FAST_PATH_ENABLED")
    agentic_gate_max_iterations: int = Field(default=4, alias="AGENTIC_GATE_MAX_ITERATIONS")
    agentic_gate_early_stop_confidence: float = Field(default=0.90, alias="AGENTIC_GATE_EARLY_STOP_CONFIDENCE")
    adaptive_reaudit_enabled: bool = Field(default=True, alias="SVR_ADAPTIVE_REAUDIT_ENABLED")
    adaptive_reaudit_category_threshold: float = Field(
        default=0.60, alias="SVR_ADAPTIVE_REAUDIT_CATEGORY_THRESHOLD"
    )
    # VoiceGate Cognitive Context Layer, 4-Layer Memory, and Classification Adjudicator
    ollama_embed_model: str = Field(default="bge-m3:latest", alias="OLLAMA_EMBED_MODEL")
    adjudicator_enabled: bool = Field(default=True, alias="SVR_ADJUDICATOR_ENABLED")
    adjudicator_conf_trigger: float = Field(default=0.68, alias="SVR_ADJUDICATOR_CONF_TRIGGER")
    adjudicator_margin_trigger: float = Field(default=0.25, alias="SVR_ADJUDICATOR_MARGIN_TRIGGER")
    adjudicator_knn_k: int = Field(default=7, alias="SVR_ADJUDICATOR_KNN_K")
    memory_enabled: bool = Field(default=True, alias="SVR_MEMORY_ENABLED")
    memory_train_seed_csv: str = Field(default="", alias="SVR_MEMORY_TRAIN_SEED_CSV")
    marbert_base_model: str = Field(default="UBC-NLP/MARBERTv2", alias="MARBERT_BASE_MODEL")
    marbert_checkpoint_seed: int = Field(default=99, alias="MARBERT_CHECKPOINT_SEED")
    onnx_max_resident_heads: int = Field(default=2, alias="SVR_ONNX_MAX_RESIDENT_HEADS")

    ffmpeg_bin: str = Field(default="ffmpeg", alias="FFMPEG_BIN")
    ffprobe_bin: str = Field(default="ffprobe", alias="FFPROBE_BIN")

    svr_bootstrap_password: str = Field(
        default="SvrTelecom2026!", alias="SVR_BOOTSTRAP_PASSWORD"
    )
    svr_cookie_secure: bool = Field(default=False, alias="SVR_COOKIE_SECURE")
    svr_trust_proxy: bool = Field(default=False, alias="SVR_TRUST_PROXY")
    svr_metrics_token: str = Field(default="", alias="SVR_METRICS_TOKEN")
    svr_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="SVR_CORS_ORIGINS",
    )

    session_inactivity_hours: int = 8
    session_cookie_name: str = "svr_session"
    csrf_cookie_name: str = "svr_csrf"

    def model_post_init(self, __context: object) -> None:
        is_prod = self.svr_env.lower() == "production"
        placeholder_secrets = {
            "",
            "replace-with-32-byte-random-secret",
            "replace-with-url-safe-base64-fernet-key",
        }
        placeholder_passwords = {"", "SvrTelecom2026!", "ChangeMeTelecom2026!"}
        self.svr_storage_dir = Path(self.svr_storage_dir)
        self.svr_models_dir = Path(self.svr_models_dir)
        self.svr_storage_dir.mkdir(parents=True, exist_ok=True)
        (self.svr_storage_dir / "voicemails").mkdir(parents=True, exist_ok=True)

        dev_keys: dict[str, str] = {}
        dev_keys_file = self.svr_storage_dir / ".dev_keys.json"
        if not is_prod and (
            self.svr_secret_key in placeholder_secrets
            or self.svr_encryption_key in placeholder_secrets
        ):
            if dev_keys_file.is_file():
                try:
                    loaded = json.loads(dev_keys_file.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        dev_keys = {str(k): str(v) for k, v in loaded.items()}
                except (OSError, ValueError):
                    dev_keys = {}

        changed_dev_keys = False
        if self.svr_secret_key in placeholder_secrets:
            if is_prod:
                raise RuntimeError("SVR_SECRET_KEY must be set to a strong non-default secret in production")
            if dev_keys.get("svr_secret_key"):
                self.svr_secret_key = dev_keys["svr_secret_key"]
            else:
                self.svr_secret_key = secrets.token_urlsafe(32)
                dev_keys["svr_secret_key"] = self.svr_secret_key
                changed_dev_keys = True
        if self.svr_encryption_key in placeholder_secrets:
            if is_prod:
                raise RuntimeError("SVR_ENCRYPTION_KEY must be set to a strong non-default Fernet key in production")
            if dev_keys.get("svr_encryption_key"):
                self.svr_encryption_key = dev_keys["svr_encryption_key"]
            else:
                self.svr_encryption_key = _derive_dev_fernet_key(self.svr_secret_key)
                dev_keys["svr_encryption_key"] = self.svr_encryption_key
                changed_dev_keys = True

        if not is_prod and changed_dev_keys:
            try:
                dev_keys_file.write_text(json.dumps(dev_keys, indent=2), encoding="utf-8")
            except OSError as exc:
                logging.getLogger("svr_platform.config").warning(
                    "Unable to persist local dev keys to %s: %s", dev_keys_file, exc
                )

        if is_prod and self.svr_bootstrap_password in placeholder_passwords:
            raise RuntimeError("SVR_BOOTSTRAP_PASSWORD must be changed from the default in production")
        if is_prod and "*" in self.cors_origins_list:
            raise RuntimeError("Wildcard CORS origins are forbidden in production")

        # Keep HuggingFace and Torch caches local to repo unless configured in environment
        cache_root = _REPO_ROOT / ".cache"
        os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
        os.environ.setdefault("TORCH_HOME", str(cache_root / "torch"))

        from .services.transcript_gate import validate_loopback_url

        self.ollama_url = validate_loopback_url(self.ollama_url)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.svr_cors_origins.split(",") if o.strip()]

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
