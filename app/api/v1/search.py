import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.retrieval import RetrievalService

router = APIRouter(prefix="/search", tags=["search"])
logger = structlog.get_logger(__name__)


@router.post("", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    logger.info(
        "search request",
        collection=request.collection,
        query=request.query[:80],
        top_k=request.top_k,
    )
    retrieval = RetrievalService(db)
    return await retrieval.search(
        query=request.query,
        collection=request.collection,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
    )
