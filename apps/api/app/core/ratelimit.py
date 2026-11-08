"""Small in-process rate limiter (sliding window per client + route).

Good enough for one API instance; behind several instances this moves to
Redis. Applied to chat, uploads, registry lookups and console login.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def limit(max_calls: int, per_seconds: int):
    def dependency(request: Request) -> None:
        from app.core.config import get_settings

        if not get_settings().rate_limit_enabled:
            return
        client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        key = f"{client}:{request.url.path.split('/')[3] if len(request.url.path.split('/')) > 3 else ''}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > per_seconds:
                q.popleft()
            if len(q) >= max_calls:
                raise HTTPException(429, "Too many requests. Please wait a moment and try again.")
            q.append(now)

    return dependency


def reset() -> None:
    with _lock:
        _hits.clear()
