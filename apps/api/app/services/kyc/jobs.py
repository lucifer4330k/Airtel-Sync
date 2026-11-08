"""Running the KYC pipeline off the request path.

KYC_QUEUE=rq     -> enqueue on Redis; the `worker` service (docker compose) runs it
KYC_QUEUE=inline -> FastAPI background task in the API process (dev, tests)
"""

import logging
import threading
from collections import defaultdict

from fastapi import BackgroundTasks
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

log = logging.getLogger(__name__)

# One check at a time per business. Uploads arrive in bursts (four documents
# in a few seconds); without this, overlapping runs each OCR the documents
# the others haven't saved yet. Serialised, every document is read once and
# later runs reuse the saved analysis.
_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock_for(business_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks[business_id]


def run_case(business_id: int, session_factory: sessionmaker | None = None) -> str:
    from app.db import SessionLocal
    from app.services.kyc.case import process_case

    with _lock_for(business_id), (session_factory or SessionLocal)() as db:
        result = process_case(db, business_id)
        db.commit()
        return result


def dispatch(background: BackgroundTasks, business_id: int, session_factory: sessionmaker) -> None:
    s = get_settings()
    if s.kyc_queue == "rq":
        try:
            from redis import Redis
            from rq import Queue

            Queue("kyc", connection=Redis.from_url(s.redis_url)).enqueue(
                run_case, business_id, job_timeout=300
            )
            return
        except Exception as exc:  # noqa: BLE001 - fall back so the owner is never stuck
            log.warning("RQ unavailable (%s); processing inline", exc.__class__.__name__)
    background.add_task(run_case, business_id, session_factory)
