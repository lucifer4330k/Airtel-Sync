"""Load the case CSVs into Postgres.

Run from apps/api after `alembic upgrade head`:
    uv run python ../../scripts/seed_db.py

Idempotent: wipes products / businesses / leads and reloads them.
The GST and Udyam registries stay as CSVs behind the mock lookup APIs.
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import delete  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Business, Lead, Product  # noqa: E402
from app.services.catalogue import SEGMENT_CODES, get_catalogue  # noqa: E402


def main() -> None:
    data = get_settings().data_dir
    with SessionLocal() as db, db.begin():
        db.execute(delete(Lead))
        db.execute(delete(Business))
        db.execute(delete(Product))

        for p in get_catalogue().values():
            db.add(
                Product(
                    product_id=p.product_id, name=p.name, category=p.category,
                    description=p.description, unit=p.unit, price_min=p.price_min,
                    price_max=p.price_max, setup_fee=p.setup_fee,
                    min_contract_months=p.min_contract_months, tiers=list(p.tiers),
                    min_employees=p.min_employees, min_sites=p.min_sites,
                    requires_gstin=p.requires_gstin, requires_one_of=list(p.requires_one_of),
                    install_days=p.install_days, segments=list(p.segments),
                )
            )
        db.flush()

        n = 0
        with (data / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                biz = Business(
                    name=row["business_name"],
                    type=row["business_type"],
                    segment=SEGMENT_CODES[row["segment"]],
                    city=row["city"],
                    tier=int(row["city_tier"]),
                    state=row["state"],
                    language=row["preferred_language"],
                    employees=int(row["employee_count"]),
                    sites=int(row["num_sites"]),
                    turnover_band=row["annual_turnover_band"],
                    gstin=row["gstin"] or None,
                    udyam_number=row["udyam_number"] or None,
                    current_internet=row["current_internet"],
                    telecom_spend=int(row["monthly_telecom_spend_inr"] or 0),
                )
                db.add(biz)
                db.flush()
                db.add(
                    Lead(
                        external_id=row["lead_id"],
                        business_id=biz.id,
                        source=row["lead_source"],
                        stage=row["stage_reached"],
                        outcome=row["outcome"] or None,
                        drop_reason=row["drop_reason"] or None,
                        products_of_interest=[
                            p for p in row["products_of_interest"].split(";") if p
                        ],
                        created_at=date.fromisoformat(row["created_date"]),
                    )
                )
                n += 1
    print(f"Seeded {len(get_catalogue())} products and {n} businesses/leads.")


if __name__ == "__main__":
    main()
