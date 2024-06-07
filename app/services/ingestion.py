import hashlib
import mimetypes
import uuid
from pathlib import Path

import structlog
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chunk import Chunk
from app.models.document import Document, IngestionStatus
from app.services.embedding import EmbeddingService

logger = structlog.get_logger(__name__)
settings = get_settings()


class IngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_service = EmbeddingService()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    async def ingest(self, document: Document) -> None:
        log = logger.bind(document_id=str(document.id), title=document.title)
        log.info("ingestion started")

        try:
            await self._set_status(document, IngestionStatus.processing)

            raw_text = self._extract_text(document.file_path, document.mime_type)
            if not raw_text.strip():
                raise ValueError("document produced no extractable text")

            chunks = self.splitter.split_text(raw_text)
            chunks = [c for c in chunks if len(c.strip()) >= settings.chunk_min_length]

            if not chunks:
                raise ValueError("no usable chunks after splitting")

            log.info("chunks produced", count=len(chunks))

            embeddings = self.embedding_service.embed_batch(chunks)

            chunk_rows = [
                Chunk(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    collection=document.collection,
                    chunk_index=i,
                    content=text,
                    token_count=len(text.split()),
                    embedding=emb,
                )
                for i, (text, emb) in enumerate(zip(chunks, embeddings))
            ]

            self.db.add_all(chunk_rows)
            document.chunk_count = len(chunk_rows)
            await self._set_status(document, IngestionStatus.completed)
            await self.db.commit()

            log.info("ingestion completed", chunk_count=len(chunk_rows))

        except Exception as exc:
            log.error("ingestion failed", error=str(exc))
            document.error_message = str(exc)
            await self._set_status(document, IngestionStatus.failed)
            await self.db.commit()
            raise

    def _extract_text(self, file_path: str, mime_type: str) -> str:
        path = Path(file_path)

        if mime_type == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            )

        if mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            from docx import Document as DocxDocument
            doc = DocxDocument(path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

        return path.read_text(encoding="utf-8", errors="replace")

    async def _set_status(self, document: Document, status: IngestionStatus) -> None:
        document.status = status
        self.db.add(document)
        await self.db.flush()
