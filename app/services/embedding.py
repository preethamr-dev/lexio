from functools import lru_cache

import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class EmbeddingService:
    _model: SentenceTransformer | None = None

    def __init__(self) -> None:
        if EmbeddingService._model is None:
            logger.info("loading embedding model", model=settings.embedding_model)
            EmbeddingService._model = SentenceTransformer(settings.embedding_model)
            logger.info("embedding model loaded")

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
