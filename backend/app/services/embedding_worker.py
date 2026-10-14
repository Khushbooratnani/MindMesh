from app.config import settings
from app.db.postgres import PostgresRepository
from app.services.embedding_service import EmbeddingService


class EmbeddingWorker:
    def __init__(
        self,
        repository: PostgresRepository | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.repository = repository or PostgresRepository()
        self.embedding_service = embedding_service or EmbeddingService()

    def run(
        self,
        limit: int = 25,
        memory_ids: list[str] | None = None,
    ) -> dict:
        rows = self.repository.fetch_embedding_inputs(
            embedding_model=settings.embedding_model,
            limit=limit,
            memory_ids=memory_ids or [],
        )
        processed = 0
        failed = 0
        errors: list[str] = []

        for row in rows:
            memory_id = row["memory_id"]
            text_for_embedding = row["text_for_embedding"]
            try:
                embedding = self.embedding_service.embed_text(text_for_embedding)
                self.repository.upsert_embedding(
                    memory_id=memory_id,
                    embedding_model=settings.embedding_model,
                    embedding=embedding,
                    embedded_text=text_for_embedding,
                )
                self.repository.mark_embedding_job_completed(memory_id, settings.embedding_model)
                processed += 1
            except Exception as exc:
                failed += 1
                message = f"{memory_id}: {exc}"
                errors.append(message)
                self.repository.mark_embedding_job_failed(
                    memory_id,
                    settings.embedding_model,
                    str(exc),
                )

        return {
            "processed": processed,
            "failed": failed,
            "embedding_model": settings.embedding_model,
            "errors": errors,
        }
