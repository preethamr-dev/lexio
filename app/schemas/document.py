import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    filename: str
    collection: str
    status: str
    file_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentUploadResponse):
    mime_type: str
    chunk_count: int
    error_message: str | None
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentDetail]
    total: int
    page: int
    page_size: int


class IngestRequest(BaseModel):
    document_id: uuid.UUID


class IngestStatusResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    chunk_count: int
    error_message: str | None
