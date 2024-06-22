import time

import structlog
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.core.config import get_settings
from app.schemas.query import QueryResponse, SourceChunk

logger = structlog.get_logger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are a precise technical assistant for an enterprise knowledge base.
Answer the user's question using only the provided context passages.
If the context does not contain enough information to answer, say so clearly.
Do not fabricate information. Cite the most relevant passages in your reasoning."""

CONTEXT_TEMPLATE = """Context passage {index} (from: {title}, section {chunk_index}):
{content}"""

QUERY_TEMPLATE = """Context:
{context}

Question: {question}

Provide a clear, accurate answer based strictly on the context above."""


class GenerationService:
    def __init__(self) -> None:
        self._llm = self._build_llm()

    def _build_llm(self):
        if settings.llm_provider == "openai":
            return ChatOpenAI(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                api_key=settings.openai_api_key,
                timeout=settings.llm_timeout_seconds,
            )
        if settings.llm_provider == "azure":
            return AzureChatOpenAI(
                azure_deployment=settings.azure_openai_deployment,
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout_seconds,
            )
        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            num_predict=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )

    async def generate(
        self,
        question: str,
        collection: str,
        retrieved_rows: list,
    ) -> QueryResponse:
        start = time.monotonic()

        if not retrieved_rows:
            return QueryResponse(
                answer="No relevant documents were found in the knowledge base for this query.",
                sources=[],
                question=question,
                collection=collection,
                latency_ms=0,
            )

        context_blocks = [
            CONTEXT_TEMPLATE.format(
                index=i + 1,
                title=row.title,
                chunk_index=row.chunk_index,
                content=row.content,
            )
            for i, row in enumerate(retrieved_rows)
        ]
        context = "\n\n".join(context_blocks)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=QUERY_TEMPLATE.format(context=context, question=question)),
        ]

        response = await self._llm.ainvoke(messages)
        answer = response.content.strip()

        sources = [
            SourceChunk(
                document_id=row.document_id,
                chunk_id=row.chunk_id,
                title=row.title,
                chunk_index=row.chunk_index,
                score=float(row.score),
                excerpt=row.content[:400],
            )
            for row in retrieved_rows
        ]

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "generation completed",
            collection=collection,
            sources=len(sources),
            latency_ms=latency_ms,
        )

        return QueryResponse(
            answer=answer,
            sources=sources,
            question=question,
            collection=collection,
            latency_ms=latency_ms,
        )
