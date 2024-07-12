import time

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["health"])
logger = structlog.get_logger(__name__)
settings = get_settings()
_start_time = time.time()


@router.get("/live")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    checks: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "uptime_seconds": int(time.time() - _start_time),
        "version": "1.0.0",
        "environment": settings.app_env,
    }
