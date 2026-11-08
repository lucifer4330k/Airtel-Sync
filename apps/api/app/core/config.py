from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> repo root is four levels up locally.
# Inside the container the file sits at /app/app/core/, so fall back to "/"
# (DATA_DIR is set explicitly there anyway).
_parents = Path(__file__).resolve().parents
_REPO_ROOT = _parents[4] if len(_parents) > 4 else Path("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_REPO_ROOT / ".env", ".env"), extra="ignore")

    # "production" turns weak or missing secrets into a startup error.
    environment: Literal["development", "production"] = "development"
    # First boot on an empty database: create the schema data and demo accounts.
    seed_on_start: bool = False
    # Nightly KYC image purge inside the API process (free hosts have no cron).
    run_purge_in_api: bool = True
    purge_interval_hours: int = 24

    database_url: str = "postgresql+psycopg://udyam:udyam@127.0.0.1:5432/udyam"
    redis_url: str = "redis://127.0.0.1:6379/0"
    data_dir: Path = _REPO_ROOT / "data"

    # The case README fixes "today" for every date-based check.
    reference_date: date = date(2026, 7, 15)

    field_encryption_key: str = ""
    jwt_secret: str = "change-me"
    cors_origins: str = "http://localhost:3000"
    # Optional regex for extra origins, e.g. Vercel preview URLs: https://udyam-.*\.vercel\.app
    cors_origin_regex: str = ""

    mock_registry_min_delay_ms: int = 300
    mock_registry_max_delay_ms: int = 800

    # KYC document storage. "local" writes to storage_dir (dev/tests); "s3" uses
    # any S3-compatible private bucket. Either way the API encrypts every file
    # with FIELD_ENCRYPTION_KEY before it is stored.
    storage_backend: Literal["local", "s3"] = "local"
    storage_dir: Path = _REPO_ROOT / ".storage"
    s3_endpoint: str = "http://127.0.0.1:8333"
    s3_bucket: str = "kyc-documents"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    # Where KYC OCR runs: "inline" (API background task) or "rq" (worker service).
    kyc_queue: Literal["inline", "rq"] = "inline"
    # Hard ceiling on how long a document image is kept (DPDP retention).
    document_retention_days: int = 30

    # Where tracker / quote links in WhatsApp messages point.
    public_web_url: str = "http://localhost:3000"

    # LLM for the advisor. Without a key the advisor runs on the rule-based
    # extractor, so the demo never depends on a network call.
    llm_provider: Literal["gemini", "openai", "none"] = "gemini"
    google_api_key: str = ""
    openai_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_model: str = "gpt-4o-mini"

    # Test-mode integrations (all optional; mocked when empty).
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "udyam-dev-verify"
    whatsapp_app_secret: str = ""
    # Local demo only: accept unsigned webhook posts when no app secret is set.
    whatsapp_allow_unsigned: bool = False

    # Console sessions
    console_token_minutes: int = 480
    rate_limit_enabled: bool = True

    @field_validator("database_url")
    @classmethod
    def _psycopg3(cls, v: str) -> str:
        """Hosted Postgres hands out postgres:// URLs; we ship the psycopg (v3) driver."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    def problems(self) -> list[str]:
        """Configuration that is unsafe to run with. Fatal in production, warned in dev."""
        out = []
        if len(self.jwt_secret) < 32 or self.jwt_secret == "change-me":
            out.append("JWT_SECRET must be a random string of at least 32 characters")
        try:
            from cryptography.fernet import Fernet

            Fernet(self.field_encryption_key.encode())
        except Exception:  # noqa: BLE001
            out.append("FIELD_ENCRYPTION_KEY is missing or not a valid Fernet key")
        if "*" in self.cors_origin_list:
            out.append("CORS_ORIGINS must list your web app's URL, not *")
        return out

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
