import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document import Document, IngestionStatus
from app.services.ingestion import IngestionService


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def sample_document(tmp_path):
    content = "This is a sample document.\n\nIt has multiple paragraphs for chunking." * 20
    file_path = tmp_path / "sample.txt"
    file_path.write_text(content)
    return Document(
        id=uuid.uuid4(),
        title="Test Doc",
        filename="sample.txt",
        file_path=str(file_path),
        collection="test",
        mime_type="text/plain",
        file_size_bytes=len(content),
        status=IngestionStatus.pending,
    )


@patch("app.services.ingestion.EmbeddingService")
def test_ingestion_produces_chunks(mock_embedding_cls, mock_db, sample_document):
    mock_embedding = mock_embedding_cls.return_value
    mock_embedding.embed_batch.return_value = [[0.1] * 384] * 50

    import asyncio
    service = IngestionService(mock_db)
    asyncio.run(service.ingest(sample_document))

    assert mock_db.add_all.called
    chunks = mock_db.add_all.call_args[0][0]
    assert len(chunks) > 0
    assert all(c.collection == "test" for c in chunks)
    assert sample_document.status == IngestionStatus.completed


@patch("app.services.ingestion.EmbeddingService")
def test_empty_document_sets_failed_status(mock_embedding_cls, mock_db, tmp_path):
    mock_embedding_cls.return_value.embed_batch.return_value = []

    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("   ")
    doc = Document(
        id=uuid.uuid4(),
        title="Empty",
        filename="empty.txt",
        file_path=str(empty_file),
        collection="test",
        mime_type="text/plain",
        file_size_bytes=3,
        status=IngestionStatus.pending,
    )

    import asyncio
    service = IngestionService(mock_db)
    with pytest.raises(ValueError):
        asyncio.run(service.ingest(doc))

    assert doc.status == IngestionStatus.failed
    assert doc.error_message is not None
