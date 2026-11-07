"""In-memory mock GST and Udyam registries, backed by the case CSVs."""

import csv
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


def _load(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return {row[key].strip().upper(): row for row in csv.DictReader(f)}


@lru_cache
def gstin_registry() -> dict[str, dict[str, str]]:
    return _load(get_settings().data_dir / "mock_gstin_registry.csv", "gstin")


@lru_cache
def udyam_registry() -> dict[str, dict[str, str]]:
    return _load(get_settings().data_dir / "mock_udyam_registry.csv", "udyam_number")


def lookup_gstin(gstin: str) -> dict[str, str] | None:
    return gstin_registry().get(gstin.strip().upper())


def lookup_udyam(number: str) -> dict[str, str] | None:
    return udyam_registry().get(number.strip().upper())


def gstin_is_active(gstin: str | None) -> bool:
    """True only for a registry record with status Active."""
    if not gstin:
        return False
    rec = lookup_gstin(gstin)
    return rec is not None and rec["status"] == "Active"
