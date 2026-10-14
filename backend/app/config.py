from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    memory_extraction_model: str = "mock-memory-extractor"
    image_understanding_model: str = "to-be-decided"
    locationiq_api_key: str | None = None
    whisper_model: str = "base"
    max_text_length: int = 20_000
    max_image_size_mb: int = 100
    max_audio_size_mb: int = 25
    database_url: str = "postgresql://postgres:postgres@localhost:5432/mindmesh"
    pgvector_table: str = "memory_embeddings"
    embedding_input_view: str = "memory_embedding_inputs"
    ollama_base_url: str = "http://localhost:11434"
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3:latest"
    embedding_dimensions: int = 1024
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "change_me"
    neo4j_database: str = "neo4j"
    graph_extraction_model: str = "mock-memory-extractor"
    graph_batch_size: int = 25

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
