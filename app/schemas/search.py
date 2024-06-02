import uuid
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    collection: str = Field(..., min_length=1, max_length=256)
    top_k: int = Field(default=8, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    chunk_index: int
    score: float
    excerpt: str
    collection: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    collection: str
    total: int
    latency_ms: int
