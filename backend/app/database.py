"""Database connection and session management."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from backend.app.config import get_settings

settings = get_settings()
database_url = settings.database_url or "sqlite:///./orc_pro.db"

connect_args = {}
if database_url.startswith("sqlite:"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    database_url,
    echo=settings.database_echo,
    future=True,
    connect_args=connect_args,
)

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
    """Create database tables if they do not exist."""
    from backend.app.models.checklist import Base as ChecklistBase

    ChecklistBase.metadata.create_all(bind=engine)
