from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> repo root is four levels up locally.
# Inside the container the file sits at /app/app/core/, so fall back to "/"
# (DATA_DIR is set explicitly there anyway).
_parents = Path(__file__).resolve().parents
_REPO_ROOT = _parents[4] if len(_parents) > 4 else Path("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_REPO_ROOT / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://udyam:udyam@localhost:5432/udyam"
    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = _REPO_ROOT / "data"

    # The case README fixes "today" for every date-based check.
    reference_date: date = date(2026, 7, 15)

    field_encryption_key: str = ""
    jwt_secret: str = "change-me"
    cors_origins: str = "http://localhost:3000"

    mock_registry_min_delay_ms: int = 300
    mock_registry_max_delay_ms: int = 800

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
