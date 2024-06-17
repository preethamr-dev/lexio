import time
import uuid

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.search import SearchResponse, SearchResult
from app.services.embedding import EmbeddingService

logger = structlog.get_logger(__name__)
settings = get_settings()


class RetrievalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_service = EmbeddingService()

    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 8,
        score_threshold: float = 0.0,
    ) -> SearchResponse:
        start = time.monotonic()

        query_embedding = self.embedding_service.embed(query)

        rows = await self._vector_search(query_embedding, collection, top_k, score_threshold)

        results = [
            SearchResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                title=row.title,
                chunk_index=row.chunk_index,
                score=float(row.score),
                excerpt=row.content[:500],
                collection=collection,
            )
            for row in rows
        ]

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "search completed",
            collection=collection,
            results=len(results),
            latency_ms=latency_ms,
        )

        return SearchResponse(
            results=results,
            query=query,
            collection=collection,
            total=len(results),
            latency_ms=latency_ms,
        )

    async def retrieve_chunks(
        self,
        query_embedding: list[float],
        collection: str,
        top_k: int,
        score_threshold: float,
    ) -> list:
        return await self._vector_search(query_embedding, collection, top_k, score_threshold)

    async def _vector_search(
        self,
        embedding: list[float],
        collection: str,
        top_k: int,
        score_threshold: float,
    ) -> list:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        stmt = text(
            """
            SELECT
                c.id          AS chunk_id,
                c.document_id AS document_id,
                c.chunk_index AS chunk_index,
                c.content     AS content,
                d.title       AS title,
                1 - (c.embedding <=> :embedding ::vector) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.collection = :collection
              AND d.status = 'completed'
              AND 1 - (c.embedding <=> :embedding ::vector) >= :threshold
            ORDER BY c.embedding <=> :embedding ::vector
            LIMIT :top_k
            """
        )

        result = await self.db.execute(
            stmt,
            {
                "embedding": embedding_str,
                "collection": collection,
                "threshold": score_threshold,
                "top_k": top_k,
            },
        )
        return result.fetchall()
