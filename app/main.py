from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import documents, health, query, search
from app.core.config import get_settings
from app.core.database import create_tables
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting lexio", env=settings.app_env)
    await create_tables()
    yield
    logger.info("shutting down lexio")


app = FastAPI(
    title="lexio",
    description="Enterprise document intelligence platform with RAG",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(documents.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "lexio", "version": "1.0.0", "docs": "/docs"}
