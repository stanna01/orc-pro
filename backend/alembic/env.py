from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect them
from backend.app.database import Base  # noqa: F401, E402
import backend.app.models.checklist  # noqa: F401, E402 — registers all ORM classes

target_metadata = Base.metadata


def _get_url() -> str:
    """Prefer DATABASE_URL from app settings; fall back to alembic.ini value."""
    try:
        from backend.app.config import get_settings
        url = get_settings().database_url
        if url:
            return url
    except Exception:
        pass
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Emit migration SQL without a live DB connection."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live DB connection."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
