"""Loads product_catalogue.csv into immutable Product records.

The rules engine reads the CSV directly (not the DB) so it is deterministic,
fast, and testable without Postgres.
"""

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

# Lead-data segment names -> catalogue segment codes
SEGMENT_CODES: dict[str, str] = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}


@dataclass(frozen=True)
class Product:
    product_id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup_fee: int
    min_contract_months: int
    tiers: tuple[int, ...]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]
    install_days: int
    segments: tuple[str, ...]


def _split(value: str, sep: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(sep) if v.strip())


def parse_row(row: dict[str, str]) -> Product:
    return Product(
        product_id=row["product_id"],
        category=row["category"],
        name=row["product_name"],
        description=row["description"],
        unit=row["unit"],
        price_min=int(row["price_min_inr_per_month"]),
        price_max=int(row["price_max_inr_per_month"]),
        setup_fee=int(row["one_time_setup_inr"]),
        min_contract_months=int(row["min_contract_months"]),
        tiers=tuple(int(t) for t in _split(row["available_city_tiers"], ";")),
        min_employees=int(row["min_employees"]),
        min_sites=int(row["min_sites"]),
        requires_gstin=row["requires_gstin"].strip().upper() == "Y",
        requires_one_of=_split(row["requires_one_of"], "|"),
        install_days=int(row["typical_install_days"]),
        segments=_split(row["target_segments"], ";"),
    )


def load_catalogue(path: Path) -> dict[str, Product]:
    with path.open(encoding="utf-8", newline="") as f:
        return {p.product_id: p for p in map(parse_row, csv.DictReader(f))}


@lru_cache
def get_catalogue() -> dict[str, Product]:
    return load_catalogue(get_settings().data_dir / "product_catalogue.csv")
