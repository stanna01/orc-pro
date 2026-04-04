"""Configuration management using Pydantic Settings.

Loads environment variables from .env file and provides typed access
to all configuration values with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    app_name: str = Field(default="ORC Pro", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment: development, staging, production, testing")

    # API
    api_title: str = Field(default="ORC Pro API", description="API title")
    api_version: str = Field(default="0.1.0", description="API version")
    api_description: str = Field(
        default="OCR and operational intelligence for mining checklists",
        description="API description"
    )

    # Server
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=False, description="Auto-reload on code changes")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="CORS allowed origins"
    )
    cors_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_methods: list[str] = Field(default=["*"], description="CORS allowed methods")
    cors_headers: list[str] = Field(default=["*"], description="CORS allowed headers")

    # Database
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection string (postgresql://user:password@host:port/dbname)"
    )
    database_echo: bool = Field(default=False, description="Log SQL queries")
    database_pool_size: int = Field(default=5, description="Database connection pool size")
    database_max_overflow: int = Field(default=10, description="Max overflow connections")

    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production", description="Secret key for JWT")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Token expiry in minutes")

    # Redis
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection string (redis://host:port/db)"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="json",
        description="Log format: json or text"
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


def get_settings() -> Settings:
    """Get application settings instance.

    Returns:
        Settings: Configuration object with all environment variables loaded.
    """
    return Settings()
