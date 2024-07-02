import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.query import QueryRequest, QueryResponse
from app.services.embedding import EmbeddingService
from app.services.generation import GenerationService
from app.services.retrieval import RetrievalService

router = APIRouter(prefix="/query", tags=["query"])
logger = structlog.get_logger(__name__)


@router.post("", response_model=QueryResponse)
async def query_knowledge_base(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    log = logger.bind(collection=request.collection, question=request.question[:80])
    log.info("query received")

    retrieval = RetrievalService(db)
    embedding_service = EmbeddingService()

    query_embedding = embedding_service.embed(request.question)

    rows = await retrieval.retrieve_chunks(
        query_embedding=query_embedding,
        collection=request.collection,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
    )

    if not rows:
        log.info("no chunks retrieved above threshold")

    generation = GenerationService()
    response = await generation.generate(
        question=request.question,
        collection=request.collection,
        retrieved_rows=rows,
    )

    log.info("query completed", latency_ms=response.latency_ms, sources=len(response.sources))
    return response
