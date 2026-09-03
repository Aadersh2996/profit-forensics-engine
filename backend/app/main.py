"""FastAPI application entry point for Profit Forensics Engine."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.datasets import router as datasets_router
from app.api.investigations import router as investigations_router
from app.config import settings
from app.db.init_db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize local infrastructure needed by the MVP API."""

    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("%s started in %s", settings.app_name, settings.environment)
    yield
    logger.info("%s shut down", settings.app_name)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(datasets_router)
app.include_router(investigations_router)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures without exposing internal details to API callers."""

    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Lightweight endpoint for local verification and deployment checks."""

    return {"status": "ok", "service": settings.app_name}
