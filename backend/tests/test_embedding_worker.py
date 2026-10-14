from app.services.embedding_worker import EmbeddingWorker


class FakeRepository:
    def __init__(self):
        self.saved = []
        self.completed = []

    def fetch_embedding_inputs(self, embedding_model, limit, memory_ids):
        return [
            {
                "memory_id": "M_1",
                "text_for_embedding": "Coffee with Akshat in Goa.",
            }
        ]

    def upsert_embedding(self, memory_id, embedding_model, embedding, embedded_text):
        self.saved.append((memory_id, embedding_model, embedding, embedded_text))

    def mark_embedding_job_completed(self, memory_id, embedding_model):
        self.completed.append((memory_id, embedding_model))

    def mark_embedding_job_failed(self, memory_id, embedding_model, error):
        raise AssertionError("No embedding job should fail in this test.")


class FakeEmbeddingService:
    def embed_text(self, text):
        return [0.1, 0.2, 0.3]


def test_embedding_worker_embeds_and_saves_rows():
    repository = FakeRepository()

    result = EmbeddingWorker(
        repository=repository,
        embedding_service=FakeEmbeddingService(),
    ).run(limit=25)

    assert result["processed"] == 1
    assert result["failed"] == 0
    assert repository.saved[0][0] == "M_1"
    assert repository.saved[0][2] == [0.1, 0.2, 0.3]
    assert repository.completed[0][0] == "M_1"
