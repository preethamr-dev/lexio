import mimetypes
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.document import Document, IngestionStatus
from app.schemas.document import DocumentDetail, DocumentListResponse, DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])
logger = structlog.get_logger(__name__)
settings = get_settings()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=512),
    collection: str = Form(..., min_length=1, max_length=256),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    extension = Path(file.filename or "").suffix.lstrip(".").lower()
    if extension not in settings.allowed_extension_set:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '.{extension}' is not supported. Allowed: {settings.allowed_extensions}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb}MB",
        )

    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    dest = upload_path / f"{doc_id}.{extension}"
    dest.write_bytes(content)

    mime_type, _ = mimetypes.guess_type(file.filename or "")
    mime_type = mime_type or "application/octet-stream"

    document = Document(
        id=doc_id,
        title=title,
        filename=file.filename or "",
        file_path=str(dest),
        collection=collection,
        mime_type=mime_type,
        file_size_bytes=len(content),
        status=IngestionStatus.pending,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    logger.info("document uploaded", id=str(doc_id), title=title, collection=collection)

    from app.worker.tasks import run_ingestion
    run_ingestion.delay(str(doc_id))

    return DocumentUploadResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    query = select(Document)
    if collection:
        query = query.where(Document.collection == collection)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Document.created_at.desc())
    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentDetail.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentDetail:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentDetail.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(document)
    await db.commit()
    logger.info("document deleted", id=str(document_id))
