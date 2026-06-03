"""Application settings, loaded from .env via pydantic-settings.

One source of truth for every tunable. Reading os.environ directly
elsewhere in the codebase is a smell. Everything here is environment-
driven so the exact same code runs locally (docker-compose) and in
production (Render + managed Postgres + Qdrant Cloud) — only the values
differ.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Qdrant — two ways to connect:
    #   * Local (docker-compose): QDRANT_HOST + QDRANT_PORT.
    #   * Cloud: set QDRANT_URL (https://...) and QDRANT_API_KEY; these take
    #     precedence over host/port in the vector store client.
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6334
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    # Authentication
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Embeddings — Voyage AI (hosted). No local model/torch.
    VOYAGE_API_KEY: str = ""
    VOYAGE_MODEL: str = "voyage-4-large"

    # LLM
    ANTHROPIC_API_KEY: str = ""

    # CORS — comma-separated list of allowed frontend origins. In dev the
    # Vite proxy makes requests same-origin so this isn't exercised; in
    # production it must contain the deployed frontend URL.
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        """Accept the legacy `postgres://` scheme some providers still emit.

        SQLAlchemy 2.x only recognises `postgresql://`; a managed DB that
        hands back `postgres://` would otherwise fail at engine creation.
        """
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS split into a clean list of origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
