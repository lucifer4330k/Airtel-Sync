"""WhatsApp / SMS outbox.

Uses the Meta WhatsApp Cloud API test number when WHATSAPP_TOKEN and
WHATSAPP_PHONE_NUMBER_ID are set; otherwise the message is recorded as
"mocked" so the demo and the console still show exactly what was sent.
"""

import logging

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import mask_pii, redact_tokens
from app.models import Business, Notification

log = logging.getLogger(__name__)
GRAPH_URL = "https://graph.facebook.com/v21.0/{phone_id}/messages"


def _send_whatsapp(to: str, body: str) -> bool:
    s = get_settings()
    if not (s.whatsapp_token and s.whatsapp_phone_number_id):
        return False
    try:
        r = httpx.post(
            GRAPH_URL.format(phone_id=s.whatsapp_phone_number_id),
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.warning("WhatsApp send failed: %s", exc)
        return False


def notify(db: Session, business: Business, body: str, order_id: int | None = None) -> Notification:
    phone = business.phone
    sent = bool(phone) and _send_whatsapp(phone, body)
    n = Notification(
        order_id=order_id,
        channel="whatsapp",
        to_masked=mask_pii(phone) if phone else None,
        body=redact_tokens(body),  # the token went to the owner only; never kept at rest
        status="sent" if sent else "mocked",
    )
    db.add(n)
    return n
