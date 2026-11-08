"""First-boot setup for hosted deployments (run by start.sh after migrations).

With SEED_ON_START=true and an empty database, loads the products, the
5,000 leads, console accounts and the demo owner. Never touches a database
that already has data, so restarts are safe.
"""

import logging
import os
import sys

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.seed import seed_all

log = logging.getLogger("udyam.bootstrap")


def main() -> None:
    s = get_settings()
    if not s.seed_on_start:
        return
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Product)):
            print("bootstrap: database already seeded, skipping")
            return
    password = os.environ.get("CONSOLE_DEMO_PASSWORD")
    if not password:
        if s.environment == "production":
            sys.exit("bootstrap: set CONSOLE_DEMO_PASSWORD before seeding console accounts")
        password = "udyam-demo"
    with SessionLocal() as db, db.begin():
        out = seed_all(db, password, wipe_first=False)
    print(f"bootstrap: seeded {out['leads']} leads, console accounts and the demo owner")


if __name__ == "__main__":
    main()
