"""FastAPI application entry point.

Sets up the FastAPI application with all middleware, exception handlers,
and route imports. This is the entry point for the ASGI server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
from typing import AsyncGenerator

from backend.app.config import get_settings
from backend.app.database import init_db
from backend.app.api.routes import health as health_router, checklists as checklists_router, uploads as uploads_router, ocr_processing as ocr_processing_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan: startup and shutdown events.

    Args:
        app: FastAPI application instance.

    Yields:
        None on startup, cleanup on shutdown.
    """
    # Startup
    logger.info("ORC Pro API starting up...")
    init_db()
    yield
    # Shutdown
    logger.info("ORC Pro API shutting down...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

    # Add trusted host middleware (skip in debug/test mode)
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.cors_origins
        )

    # Include routers
    app.include_router(health_router, tags=["health"])
    app.include_router(checklists_router, tags=["checklists"])
    app.include_router(uploads_router, tags=["uploads"])
    app.include_router(ocr_processing_router, tags=["ocr"])

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Handle uncaught exceptions globally.

        Args:
            request: Request object.
            exc: Exception object.

        Returns:
            JSONResponse with error details.
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if settings.debug else "An unexpected error occurred",
            },
        )

    logger.info(
        f"ORC Pro API initialized | "
        f"Environment: {settings.environment} | "
        f"Debug: {settings.debug}"
    )

    return app


# Create the FastAPI app instance
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
