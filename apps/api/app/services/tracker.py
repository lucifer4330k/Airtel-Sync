"""Order state machine, ETA and engineer slots.

Order placed -> KYC verified -> Engineer scheduled -> Installed -> Activated,
plus On hold (with a reason) from any open state. Every change writes an
order event and pushes a WhatsApp/SMS update with the tracker link.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Business, Order, OrderEvent, Quote, QuoteItem
from app.services.catalogue import get_catalogue
from app.services.notify import notify

IST = ZoneInfo("Asia/Kolkata")
STATES = ["order_placed", "kyc_verified", "engineer_scheduled", "installed", "activated"]
LABEL = {
    "order_placed": "Order placed",
    "kyc_verified": "Documents verified",
    "engineer_scheduled": "Engineer visit booked",
    "installed": "Installed",
    "activated": "Working",
    "on_hold": "On hold",
}
# Two visit windows a day, India time.
WINDOWS = [(time(10), time(13)), (time(14), time(18))]


def today() -> date:
    return get_settings().reference_date


def item_etas(db: Session, quote_id: int) -> list[dict]:
    catalogue = get_catalogue()
    items = db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote_id)).all()
    return [
        {"name": catalogue[i.product_id].name, "install_days": catalogue[i.product_id].install_days}
        for i in items
    ]


def slot_options(start: date, n_days: int = 5) -> list[dict]:
    """Next working-day windows (no Sundays), starting the day after `start`."""
    out, d = [], start
    while len(out) < n_days * len(WINDOWS):
        d += timedelta(days=1)
        if d.weekday() == 6:
            continue
        for a, b in WINDOWS:
            out.append(
                {
                    "start": datetime.combine(d, a, IST).isoformat(),
                    "end": datetime.combine(d, b, IST).isoformat(),
                }
            )
    return out


def tracker_link(order: Order, token: str) -> str:
    return f"{get_settings().public_web_url}/track/{order.id}?t={token}"


def _event(db: Session, order: Order, event: str, detail: str | None = None) -> None:
    db.add(OrderEvent(order_id=order.id, event=event, detail=detail))


def _push(db: Session, order: Order, text: str) -> None:
    from app.core.security import kyc_token

    biz = db.get(Business, order.business_id)
    link = tracker_link(order, kyc_token(order.business_id))
    notify(db, biz, f"Udyam Digital: {text} Track your order: {link}", order_id=order.id)


def create_order(db: Session, quote: Quote, business_id: int, method: str, payment_ref: str) -> Order:
    eta = today() + timedelta(days=quote.eta_days)
    order = Order(
        quote_id=quote.id,
        business_id=business_id,
        state="order_placed",
        eta_date=eta,
        payment_method=method,
        payment_ref=payment_ref,
    )
    db.add(order)
    db.flush()
    _event(db, order, "order_placed", f"Paid via {method} ({payment_ref})")
    _push(db, order, f"order #{order.id} is placed. Expected to be working by {eta:%d %b %Y}.")
    return order


def _last_open_state(db: Session, order: Order) -> str:
    events = db.scalars(
        select(OrderEvent.event).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id.desc())
    )
    return next((e for e in events if e in STATES), "order_placed")


def set_state(db: Session, order: Order, new_state: str, actor: str, reason: str | None = None) -> Order:
    if order.state == "activated":
        raise HTTPException(409, "Order is already active")
    if new_state == "on_hold":
        if not reason:
            raise HTTPException(422, "Give a reason for the hold")
        order.state, order.hold_reason = "on_hold", reason
        _event(db, order, "on_hold", f"{reason} (by {actor})")
        _push(db, order, f"order #{order.id} is on hold: {reason}. We will update you as soon as it moves.")
        return order
    if new_state not in STATES:
        raise HTTPException(422, f"Unknown state {new_state}")

    current = _last_open_state(db, order) if order.state == "on_hold" else order.state
    if STATES.index(new_state) != STATES.index(current) + 1 and not (
        order.state == "on_hold" and new_state == current
    ):
        raise HTTPException(409, f"Cannot go from {LABEL[current]} to {LABEL[new_state]}")

    order.state, order.hold_reason = new_state, None
    if new_state == "engineer_scheduled" and order.engineer_slot is None:
        first = slot_options(today())[0]
        order.engineer_slot = datetime.fromisoformat(first["start"])
    detail = f"by {actor}"
    if new_state == "engineer_scheduled":
        detail = f"{order.engineer_slot.astimezone(IST):%a %d %b, %I:%M %p} ({actor})"
    _event(db, order, new_state, detail)

    slot_text = f"{order.engineer_slot.astimezone(IST):%a %d %b, %I:%M %p}" if order.engineer_slot else ""
    msg = {
        "kyc_verified": "your documents are verified.",
        "engineer_scheduled": f"an engineer visit is booked for {slot_text}.",
        "installed": "installation is complete. We are switching your services on.",
        "activated": "your services are live. Welcome aboard!",
    }.get(new_state, LABEL[new_state])
    _push(db, order, f"order #{order.id}: {msg}")
    return order


def advance(db: Session, order: Order, actor: str) -> Order:
    current = _last_open_state(db, order) if order.state == "on_hold" else order.state
    if order.state == "on_hold":
        return set_state(db, order, current, actor)  # resume
    if current == "activated":
        raise HTTPException(409, "Order is already active")
    return set_state(db, order, STATES[STATES.index(current) + 1], actor)


def reschedule(db: Session, order: Order, start_iso: str) -> Order:
    if order.state not in ("order_placed", "kyc_verified", "engineer_scheduled"):
        raise HTTPException(409, "The visit can no longer be moved")
    valid = {s["start"] for s in slot_options(today())}
    if start_iso not in valid:
        raise HTTPException(422, "Pick one of the offered visit slots")
    order.engineer_slot = datetime.fromisoformat(start_iso)
    when = f"{order.engineer_slot.astimezone(IST):%a %d %b, %I:%M %p}"
    _event(db, order, "rescheduled", when)
    _push(db, order, f"engineer visit for order #{order.id} moved to {when}.")
    return order


def view(db: Session, order: Order) -> dict:
    events = db.scalars(
        select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id)
    ).all()
    reached = {e.event: e.at for e in events}
    open_state = _last_open_state(db, order) if order.state == "on_hold" else order.state
    return {
        "id": order.id,
        "state": order.state,
        "state_label": LABEL[order.state],
        "hold_reason": order.hold_reason,
        "eta_date": order.eta_date,
        "engineer_slot": order.engineer_slot,
        "steps": [
            {
                "state": s,
                "label": LABEL[s],
                "done": STATES.index(s) <= STATES.index(open_state),
                "current": s == open_state,
                "at": reached.get(s),
            }
            for s in STATES
        ],
        "events": [
            {"event": e.event, "label": LABEL.get(e.event, e.event), "detail": e.detail, "at": e.at}
            for e in events
        ],
        "items": item_etas(db, order.quote_id),
        "slot_options": slot_options(today()) if order.state in STATES[:3] else [],
        "created_at": order.created_at,
    }
