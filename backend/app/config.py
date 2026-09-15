from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_env: str = "development"
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    memory_extraction_model: str = "mock-memory-extractor"
    image_understanding_model: str = "to-be-decided"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    media_storage_dir: str = "media_uploads"
    max_text_length: int = 20_000
    max_image_size_mb: int = 10
    max_audio_size_mb: int = 25

    # Database configuration (PostgreSQL + asyncpg)
    database_url: str = "postgresql+asyncpg://coeai@localhost:5432/mindmesh"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    model_config = SettingsConfigDict(
        env_file=(".env", str(_BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
