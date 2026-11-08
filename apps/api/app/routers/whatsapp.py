"""WhatsApp channel: Meta Cloud API webhook into the same advisor engine.

Documents are never collected in chat; the reply carries a link that opens
the plan (and later KYC) in the web app.
"""

import hashlib
import hmac
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import mask_pii, redact_tokens
from app.core.ratelimit import limit
from app.db import get_db
from app.models import AdvisorSession, Notification
from app.services.advisor import engine
from app.services.notify import _send_whatsapp

log = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
Db = Annotated[Session, Depends(get_db)]


def _phone_key(phone: str) -> str:
    """Sessions are found by a keyed hash of the sender, never the raw number."""
    return hmac.new(get_settings().jwt_secret.encode(), phone.encode(), hashlib.sha256).hexdigest()[:32]


@router.get("/webhook", response_class=PlainTextResponse)
def verify(
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
):
    if mode == "subscribe" and token and hmac.compare_digest(token, get_settings().whatsapp_verify_token):
        return challenge or ""
    raise HTTPException(403, "Verification failed")


def _check_signature(request_body: bytes, signature: str | None) -> None:
    s = get_settings()
    secret = s.whatsapp_app_secret
    if not secret:
        # Fail closed: unsigned webhooks only with an explicit local-demo switch.
        if s.whatsapp_allow_unsigned:
            return
        raise HTTPException(503, "WhatsApp webhook is not configured")
    expected = "sha256=" + hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Bad signature")


def _format(turn: dict) -> str:
    text = turn["reply"]
    if turn.get("chips"):
        text += "\n\n" + " / ".join(turn["chips"])
    card = turn.get("bundle")
    if card:
        base = get_settings().public_web_url
        link = (
            f"{base}/resume?b={card['business_id']}&t={card['owner_token']}&q={card['recommended_quote_id']}"
        )
        text += f"\n\nOpen your plan, add services and pay: {link}"
    return text


@router.post("/webhook", dependencies=[Depends(limit(120, 60))])
async def inbound(request: Request, db: Db):
    raw = await request.body()
    _check_signature(raw, request.headers.get("x-hub-signature-256"))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid JSON") from exc

    replies = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                sender = str(msg.get("from", ""))[-10:]
                if msg.get("type") != "text" or not sender:
                    continue
                text = (msg.get("text") or {}).get("body", "")[:1000]
                key = _phone_key(sender)
                session = db.scalar(
                    select(AdvisorSession)
                    .where(
                        AdvisorSession.channel == "whatsapp", AdvisorSession.slots["wa"].as_string() == key
                    )
                    .order_by(AdvisorSession.id.desc())
                )
                if session is None:
                    session, _ = engine.start(db, "whatsapp", None)
                    session.slots = {**session.slots, "wa": key, "phone": sender}
                    db.flush()
                turn = engine.handle(db, session, text)
                session.slots = {**session.slots, "wa": key, "phone": sender}
                body = _format(turn)
                sent = _send_whatsapp(sender, body)
                db.add(
                    Notification(
                        channel="whatsapp",
                        to_masked=mask_pii(sender),
                        body=redact_tokens(body),  # the owner got the link; nobody else keeps it
                        status="sent" if sent else "mocked",
                    )
                )
                replies.append({"to": mask_pii(sender), "text": redact_tokens(body)})
    db.commit()
    # Meta only needs a 200. Replies are echoed (redacted) for the local demo only.
    if get_settings().whatsapp_allow_unsigned and not get_settings().whatsapp_app_secret:
        return {"ok": True, "replies": replies}
    return {"ok": True}
