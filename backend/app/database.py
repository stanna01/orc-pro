"""Database connection and session management."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from backend.app.config import get_settings

settings = get_settings()
database_url = settings.database_url or "sqlite:///./orc_pro.db"

connect_args = {}
_is_sqlite = database_url.startswith("sqlite:")
if _is_sqlite:
    connect_args = {"check_same_thread": False}

_engine_kwargs: dict = {
    "echo": settings.database_echo,
    "future": True,
    "connect_args": connect_args,
}
if not _is_sqlite:
    # SQLite does not support connection pool settings
    _engine_kwargs["pool_size"] = settings.database_pool_size
    _engine_kwargs["max_overflow"] = settings.database_max_overflow
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 3600

engine = create_engine(database_url, **_engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

Base = declarative_base()


def get_session() -> Generator[Session, None, None]:
    """Provide a database session to a request.

    Yields:
        Session: SQLAlchemy session instance.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create database tables if they do not exist.

    Used in tests and development. For production, call ``upgrade_db()``
    instead so schema changes are applied through Alembic migrations.
    """
    from backend.app.models.checklist import Base as ChecklistBase

    ChecklistBase.metadata.create_all(bind=engine)


def upgrade_db() -> None:
    """Run all pending Alembic migrations (idempotent).

    Applies ``alembic upgrade head`` programmatically. Safe to call at
    application startup — does nothing if the schema is already up to date.
    """
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    # alembic.ini lives in the backend/ directory
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"

    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")
