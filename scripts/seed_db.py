"""Load the case data and demo accounts into Postgres (wipes first).

Run from apps/api after `alembic upgrade head`:
    uv run python ../../scripts/seed_db.py

Seeds products, the 5,000 scored leads, console accounts (admin, rep.pune,
partner.mumbai, partner.delhi; password from CONSOLE_DEMO_PASSWORD, default
"udyam-demo" - change it outside demos) and a demo owner with a placed order.
The GST and Udyam registries stay as CSVs behind the mock lookup APIs.
"""

import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
# repo checkout (apps/api) or the API image (/app)
sys.path.insert(0, str(_root / "apps" / "api") if (_root / "apps" / "api").exists() else str(_root))

from app.db import SessionLocal  # noqa: E402
from app.seed import TEAM, seed_all  # noqa: E402


def main() -> None:
    password = os.environ.get("CONSOLE_DEMO_PASSWORD", "udyam-demo")
    with SessionLocal() as db, db.begin():
        out = seed_all(db, password, wipe_first=True)
    print(f"Seeded 25 products and {out['leads']} businesses/leads (scored).")
    print(f"Console logins: {', '.join(u for u, *_ in TEAM)}  (password from CONSOLE_DEMO_PASSWORD)")
    print(f"Demo owner tracker: {out['tracker']}")
    print(f"Demo owner plan:    {out['plan']}")


if __name__ == "__main__":
    main()
