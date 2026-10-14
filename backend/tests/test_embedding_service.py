import pytest

from app.services.embedding_service import EmbeddingError, EmbeddingService


def test_parse_embedding_validates_dimension():
    service = EmbeddingService(model_name="bge-m3:latest", dimensions=3)

    assert service._parse_embedding({"embedding": [1, "2.5", -3]}) == [1.0, 2.5, -3.0]


def test_parse_embedding_rejects_wrong_dimension():
    service = EmbeddingService(model_name="bge-m3:latest", dimensions=3)

    with pytest.raises(EmbeddingError):
        service._parse_embedding({"embedding": [1, 2]})
