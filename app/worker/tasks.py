import asyncio
import uuid

import structlog

from app.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.run_ingestion",
    max_retries=3,
    default_retry_delay=30,
)
def run_ingestion(self, document_id: str) -> dict:
    log = logger.bind(task_id=self.request.id, document_id=document_id)
    log.info("ingestion task started")

    try:
        result = asyncio.run(_ingest(document_id))
        log.info("ingestion task completed")
        return result
    except Exception as exc:
        log.error("ingestion task failed", error=str(exc), retries=self.request.retries)
        raise self.retry(exc=exc)


async def _ingest(document_id: str) -> dict:
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.document import Document
    from app.services.ingestion import IngestionService

    doc_uuid = uuid.UUID(document_id)

    async with async_session_factory() as session:
        result = await session.execute(select(Document).where(Document.id == doc_uuid))
        document = result.scalar_one_or_none()

        if document is None:
            raise ValueError(f"document {document_id} not found")

        service = IngestionService(session)
        await service.ingest(document)

    return {"document_id": document_id, "status": "completed"}
