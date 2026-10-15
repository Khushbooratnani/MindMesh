import hashlib
import numpy as np
from typing import List, Tuple, Optional, Any, Dict
from phase2_orchestration.config import settings

class EmbeddingGenerationError(Exception):
    """Raised when embedding generation fails."""
    pass

class BGEModelSingleton:
    _instance = None
    _model = None

    @classmethod
    def get_model(cls, model_name: str = "BAAI/bge-m3"):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                try:
                    cls._model = SentenceTransformer(model_name, local_files_only=True)
                except Exception:
                    cls._model = SentenceTransformer(model_name)
            except Exception as e:
                print(f" [!] BAAI/bge-m3 model loading note: {str(e)}")
                cls._model = None
        return cls._model

class EmbeddingService:
    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: int = 1024,
        force_mock: Optional[bool] = None
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        if force_mock is not None:
            self.force_mock = force_mock
        else:
            self.force_mock = settings.EMBEDDING_FORCE_MOCK

    @staticmethod
    def build_content_text(memory: Any) -> str:
        """Constructs text representation for Content Embedding ("What happened?")."""
        if isinstance(memory, dict):
            content = memory.get("content", {})
        else:
            content = getattr(memory, "content", {})
            if hasattr(content, "model_dump"):
                content = content.model_dump()
            elif hasattr(content, "dict"):
                content = content.dict()
            elif not isinstance(content, dict):
                content = {}

        raw_text = content.get("raw_text", "") or ""
        clean_text = content.get("clean_text", "") or ""
        description = content.get("description", "") or ""
        summary = content.get("summary", "") or ""

        parts = []
        if clean_text.strip():
            parts.append(clean_text.strip())
        elif raw_text.strip():
            parts.append(raw_text.strip())

        if summary.strip() and summary.strip() not in parts:
            parts.append(summary.strip())
        elif description.strip() and description.strip() not in parts:
            parts.append(description.strip())

        return "\n\n".join(parts).strip()

    @staticmethod
    def build_context_text(memory: Any) -> str:
        """Constructs text representation for Context Embedding ("Entities, Topics, Mood, Time")."""
        if isinstance(memory, dict):
            entities = memory.get("entities", {})
            semantics = memory.get("semantics", {})
            temporal = memory.get("temporal", {})
        else:
            entities = getattr(memory, "entities", {})
            semantics = getattr(memory, "semantics", {})
            temporal = getattr(memory, "temporal", {})
            
            entities = entities.model_dump() if hasattr(entities, "model_dump") else (entities.dict() if hasattr(entities, "dict") else {})
            semantics = semantics.model_dump() if hasattr(semantics, "model_dump") else (semantics.dict() if hasattr(semantics, "dict") else {})
            temporal = temporal.model_dump() if hasattr(temporal, "model_dump") else (temporal.dict() if hasattr(temporal, "dict") else {})

        lines = []

        # Entities
        people = entities.get("people") or entities.get("person")
        if people:
            lines.append(f"People: {', '.join(people) if isinstance(people, list) else str(people)}")

        places = entities.get("places") or entities.get("place")
        if places:
            lines.append(f"Place: {', '.join(places) if isinstance(places, list) else str(places)}")

        events = entities.get("events") or entities.get("event")
        if events:
            lines.append(f"Event: {', '.join(events) if isinstance(events, list) else str(events)}")

        orgs = entities.get("organizations") or entities.get("organization")
        if orgs:
            lines.append(f"Organizations: {', '.join(orgs) if isinstance(orgs, list) else str(orgs)}")

        # Semantics
        topics = semantics.get("topics")
        if topics:
            lines.append(f"Topics: {', '.join(topics) if isinstance(topics, list) else str(topics)}")

        activities = semantics.get("activities")
        if activities:
            lines.append(f"Activities: {', '.join(activities) if isinstance(activities, list) else str(activities)}")

        sentiment = semantics.get("sentiment")
        if sentiment and str(sentiment).lower() != "unknown":
            lines.append(f"Sentiment: {sentiment}")

        mood = semantics.get("mood")
        if mood:
            lines.append(f"Mood: {', '.join(mood) if isinstance(mood, list) else str(mood)}")

        time_of_day = temporal.get("time_of_day")
        if time_of_day and str(time_of_day).lower() != "unknown":
            lines.append(f"Time of Day: {time_of_day}")

        return "\n".join(lines).strip()

    def _generate_mock_vector(self, text: str) -> List[float]:
        if not text:
            text = "empty"
        md5_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        seed = int(md5_hash[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingGenerationError("Cannot generate embedding for empty text")

        if self.force_mock:
            return self._generate_mock_vector(text)

        model = BGEModelSingleton.get_model(self.model_name)
        if model is None:
            # Automatic graceful fallback to deterministic vector if model cannot be downloaded offline
            print(" [EmbeddingService] bge-m3 model unavailable, falling back to deterministic local vector.")
            return self._generate_mock_vector(text)

        try:
            embeddings = model.encode(text, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            raise EmbeddingGenerationError(f"Embedding inference failed: {str(e)}")

    def generate_content_and_context_vectors(
        self, memory: Any
    ) -> Tuple[List[float], List[float]]:
        content_text = self.build_content_text(memory)
        context_text = self.build_context_text(memory)

        if not content_text and not context_text:
            raise EmbeddingGenerationError("Memory payload contains no text for content or context embedding")

        if not content_text:
            content_text = context_text
        if not context_text:
            context_text = content_text

        content_vector = self.generate_embedding(content_text)
        context_vector = self.generate_embedding(context_text)

        if len(content_vector) != self.dimension or len(context_vector) != self.dimension:
            raise EmbeddingGenerationError(f"Embedding vector dimension mismatch. Expected {self.dimension}.")

        return content_vector, context_vector
