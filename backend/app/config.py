from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_env: str = "development"
    openai_compatible_base_url: str = "http://10.9.8.7:8128/v1"
    openai_compatible_api_key: str | None = None
    memory_extraction_model: str = "/home/llmapi/models/Qwen3.8-27B"
    image_understanding_model: str = "/home/llmapi/models/Qwen3.8-27B"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_initial_prompt: str = "MindMesh voice memo in English, Hindi, or Hinglish. Common Indian names and places may occur."
    media_storage_dir: str = "media_uploads"
    # Media constraints
    max_text_length: int = 20_000
    max_image_size_mb: int = 10
    max_audio_size_mb: int = 25

    # Phase 2 Embedding & Vector Configuration
    embedding_model: str = "BAAI/bge-m3"
    embedding_model_path: str | None = None
    embedding_dimension: int = 1024
    embedding_force_mock: bool = False
    default_content_weight: float = 0.5
    default_context_weight: float = 0.5
    search_min_relevance_score: float = 0.50

    # Database configuration (PostgreSQL + asyncpg)
    database_url: str = "postgresql+asyncpg://coeai@localhost:5432/mindmesh"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Auth configuration
    auth_secret_key: str = "default-insecure-secret-key-change-in-production"
    user_session_timeout_days: int = 30
    private_locker_idle_timeout_seconds: int = 120
    locker_encryption_key: str | None = None

    # Package B Local-First Private Locker Configuration (Feature-Gated & Secure Allowlist)
    enable_local_first_locker: bool = False
    locker_auth_database_url: str = "postgresql+asyncpg://coeai@localhost:5432/mindmesh_locker_auth"
    local_first_test_user_allowlist: list[str] = []

    model_config = SettingsConfigDict(
        env_file=(".env", str(_BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if self.app_env.lower() in ("production", "prod"):
            insecure_keys = (
                "default-insecure-secret-key-change-in-production",
                "secret",
                "changeme",
            )
            if not self.auth_secret_key or self.auth_secret_key in insecure_keys:
                raise ValueError(
                    "Production environment requires a secure AUTH_SECRET_KEY to be configured."
                )
            if not self.locker_encryption_key:
                raise ValueError(
                    "Production environment requires LOCKER_ENCRYPTION_KEY to be configured."
                )


settings = Settings()

