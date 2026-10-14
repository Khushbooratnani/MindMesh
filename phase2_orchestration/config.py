import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    
    # Optional LLM completion keys
    openai_compatible_base_url: Optional[str] = None
    openai_compatible_api_key: Optional[str] = None
    
    # PostgreSQL & pgvector Database Settings
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/mind_mesh")
    
    # BAAI/bge-m3 Embedding Model Settings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_FORCE_MOCK: bool = False
    
    # Search Vector Weights (Content vs Context)
    DEFAULT_CONTENT_WEIGHT: float = 0.5
    DEFAULT_CONTEXT_WEIGHT: float = 0.5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
