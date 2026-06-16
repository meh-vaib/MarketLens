"""Application configuration.

All values can be overridden via environment variables (see ``.env.example``).
We use Pydantic-Settings so every field is validated and typed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
REPORT_DIR = DATA_DIR / "reports"
SOURCES_FILE = ROOT_DIR / "config" / "sources.yaml"


class Settings(BaseSettings):
    """Centralised, validated configuration.

    Attributes are populated from (in order of precedence):
    1. Process environment variables.
    2. A ``.env`` file at the project root.
    3. Defaults defined here.
    """

    # --- LLM ----------------------------------------------------------------
    llm_provider: Literal["anthropic", "openai", "ollama", "groq"] = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1500

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    groq_api_key: str | None = None

    # --- Email --------------------------------------------------------------
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    # NoDecode stops the env source from JSON-parsing the value so our
    # comma-splitting validator below can handle plain "a@x.com,b@y.com".
    email_to: Annotated[list[str], NoDecode] = Field(default_factory=list)
    email_enabled: bool = True

    # --- Schedule -----------------------------------------------------------
    schedule_hour: int = 7
    schedule_minute: int = 30

    # --- Storage ------------------------------------------------------------
    database_url: str = f"sqlite:///{DATA_DIR / 'intel.db'}"

    # --- Pipeline -----------------------------------------------------------
    max_items_per_source: int = 20
    max_items_to_analyze: int = 25
    relevance_threshold: float = 0.35
    request_timeout_seconds: int = 15

    # --- Optional API keys --------------------------------------------------
    newsapi_key: str | None = None
    fred_api_key: str | None = None
    alphavantage_key: str | None = None

    # --- API server ---------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "change-me"

    # --- Logging ------------------------------------------------------------
    log_level: str = "INFO"
    log_dir: str = "logs"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Validators ---------------------------------------------------------
    @field_validator("email_to", mode="before")
    @classmethod
    def _split_email_to(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [addr.strip() for addr in v.split(",") if addr.strip()]
        return v

    # --- Helpers ------------------------------------------------------------
    def ensure_dirs(self) -> None:
        """Create runtime directories if they do not exist."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
