import uuid
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    collection: str = Field(..., min_length=1, max_length=256)
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.35, ge=0.0, le=1.0)


class SourceChunk(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    chunk_index: int
    score: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    question: str
    collection: str
    latency_ms: int
