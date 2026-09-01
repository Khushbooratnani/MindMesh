from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    memory_extraction_model: str = "mock-memory-extractor"
    image_understanding_model: str = "to-be-decided"
    whisper_model: str = "whisper-1"
    max_text_length: int = 20_000
    max_image_size_mb: int = 10
    max_audio_size_mb: int = 25

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
