"""Nightly purge of KYC images (DPDP retention).

Deletes the stored image (keeping extracted fields and check results) when:
  - its purge_after date has passed (hard ceiling, DOCUMENT_RETENTION_DAYS), or
  - the case is verified and the audit window (AUDIT_WINDOW_DAYS) has passed.

Run daily:  python -m app.workers.purge_documents
(docker compose: `docker compose run --rm worker python -m app.workers.purge_documents`;
 Render/Railway: a cron job with the same command.)
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AuditLog, Business, KycDocument
from app.services.kyc.case import case_status
from app.services.storage import get_storage

log = logging.getLogger(__name__)
AUDIT_WINDOW_DAYS = 7


def purge(db: Session, today: date | None = None) -> int:
    today = today or datetime.now(UTC).date()
    storage = get_storage()
    verified: dict[int, bool] = {}
    purged = 0
    for doc in db.scalars(select(KycDocument).where(KycDocument.storage_key.is_not(None))):
        if doc.business_id not in verified:
            verified[doc.business_id] = (
                case_status(db, db.get(Business, doc.business_id))["overall"] == "pass"
            )
        expired = doc.purge_after is not None and doc.purge_after <= today
        audit_done = (
            verified[doc.business_id] and doc.uploaded_at.date() + timedelta(days=AUDIT_WINDOW_DAYS) <= today
        )
        if expired or audit_done:
            storage.delete(doc.storage_key)
            doc.storage_key = None
            doc.extracted = {**(doc.extracted or {}), "purged_on": today.isoformat()}
            db.add(AuditLog(actor="system:purge", event="kyc.image_purged", target=f"kyc_document:{doc.id}"))
            purged += 1
    db.commit()
    return purged


def main() -> None:
    with SessionLocal() as db:
        n = purge(db)
    print(f"Purged {n} document image(s).")


if __name__ == "__main__":
    main()
