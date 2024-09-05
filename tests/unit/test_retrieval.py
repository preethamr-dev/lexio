import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.retrieval import RetrievalService


@pytest.fixture
def mock_db():
    return AsyncMock()


@patch("app.services.retrieval.EmbeddingService")
@pytest.mark.asyncio
async def test_search_returns_results(mock_embedding_cls, mock_db):
    mock_embedding_cls.return_value.embed.return_value = [0.1] * 384

    fake_row = MagicMock()
    fake_row.chunk_id = uuid.uuid4()
    fake_row.document_id = uuid.uuid4()
    fake_row.title = "Test Doc"
    fake_row.chunk_index = 0
    fake_row.score = 0.87
    fake_row.content = "This is the content of the chunk."

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [fake_row]
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = RetrievalService(mock_db)
    response = await service.search(
        query="test query",
        collection="ops",
        top_k=5,
        score_threshold=0.3,
    )

    assert response.total == 1
    assert response.results[0].score == pytest.approx(0.87)
    assert response.results[0].title == "Test Doc"
    assert response.latency_ms >= 0


@patch("app.services.retrieval.EmbeddingService")
@pytest.mark.asyncio
async def test_search_empty_collection_returns_no_results(mock_embedding_cls, mock_db):
    mock_embedding_cls.return_value.embed.return_value = [0.0] * 384

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = RetrievalService(mock_db)
    response = await service.search("anything", "empty-collection", top_k=5, score_threshold=0.5)

    assert response.total == 0
    assert response.results == []
