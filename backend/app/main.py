"""FastAPI application entry point.

Sets up the FastAPI application with all middleware, exception handlers,
and route imports. This is the entry point for the ASGI server.
"""

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from typing import AsyncGenerator

from backend.app.config import get_settings
from backend.app.database import init_db, upgrade_db
from backend.app.api.routes import (
    health as health_router,
    checklists as checklists_router,
    uploads as uploads_router,
    ocr_processing as ocr_processing_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Hard cap on inbound request body (50 MB) — evaluated before the body is
# fully read into memory, so a 2 GB upload won't OOM the server.
_MAX_REQUEST_BODY_BYTES = 50 * 1024 * 1024


class _RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request body too large",
                    "max_mb": _MAX_REQUEST_BODY_BYTES // (1024 * 1024),
                },
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan: startup and shutdown events."""
    settings = get_settings()
    logger.info("ORC Pro API starting up...")

    # Apply database schema: use Alembic migrations in production,
    # create_all in dev/test (faster, no migration history needed).
    if settings.environment == "production":
        logger.info("Running Alembic migrations (upgrade head)...")
        upgrade_db()
    else:
        init_db()

    # Probe OCR availability and warn loudly if running in simulated mode.
    try:
        from backend.app.services.ocr_extractor import initialize_ocr_extractor
        _ocr = initialize_ocr_extractor(
            fail_on_missing=(settings.environment == "production")
        )
        if _ocr.simulated:
            logger.warning(
                "STARTUP WARNING: TrOCR model is unavailable. "
                "Running in SIMULATED OCR mode — all OCR outputs are synthetic. "
                "DO NOT process real documents in this mode."
            )
    except RuntimeError as exc:
        # Only reaches here when environment=production and model is missing.
        logger.critical("TrOCR model required in production but unavailable: %s", exc)
        raise

    yield
    logger.info("ORC Pro API shutting down...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Request body size cap — must be added before CORS so it intercepts first.
    app.add_middleware(_RequestSizeLimitMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # TrustedHostMiddleware expects plain hostnames (e.g. "localhost"), NOT
    # full origins (e.g. "http://localhost:3000"). Extract hostnames from the
    # CORS origins list; skip if wildcard is present.
    if not settings.debug and "*" not in settings.cors_origins:
        allowed_hosts = [
            urlparse(o).hostname or o
            for o in settings.cors_origins
            if o and o != "*"
        ]
        allowed_hosts = list(dict.fromkeys(h for h in allowed_hosts if h))
        if allowed_hosts:
            app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Routers
    app.include_router(health_router, tags=["health"])
    app.include_router(checklists_router, tags=["checklists"])
    app.include_router(uploads_router, tags=["uploads"])
    app.include_router(ocr_processing_router, tags=["ocr"])

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception at %s", request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if settings.debug else "An unexpected error occurred",
            },
        )

    logger.info(
        "ORC Pro API initialized | Environment: %s | Debug: %s",
        settings.environment,
        settings.debug,
    )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
