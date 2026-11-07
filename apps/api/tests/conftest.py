import csv
import os

import pytest

os.environ.setdefault("MOCK_REGISTRY_MIN_DELAY_MS", "0")
os.environ.setdefault("MOCK_REGISTRY_MAX_DELAY_MS", "0")

from app.core.config import get_settings  # noqa: E402


@pytest.fixture(scope="session")
def leads() -> list[dict[str, str]]:
    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
