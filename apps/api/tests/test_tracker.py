import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Notification, Order


def placed_order(client):
    q = client.post(
        "/api/v1/quotes", json={"profile": {"segment": "micro", "city_tier": 2, "employees": 3, "sites": 1}}
    ).json()
    h = {"X-Owner-Token": q["owner_token"]}
    r = client.post(f"/api/v1/quotes/{q['quotes'][0]['id']}/accept", json={"phone": "9876543210"}, headers=h)
    return r.json()["order_id"], h


def _db():
    from app.db import get_db
    from app.main import app

    gen = app.dependency_overrides[get_db]()
    return gen, next(gen)


def test_full_lifecycle_with_hold_and_notifications(client):
    from app.services import tracker

    order_id, h = placed_order(client)
    gen, db = _db()
    try:
        order = db.get(Order, order_id)
        tracker.advance(db, order, "admin")  # kyc_verified
        tracker.set_state(db, order, "on_hold", "admin", reason="Building access pending")
        assert order.state == "on_hold"
        tracker.advance(db, order, "admin")  # resumes to kyc_verified
        assert order.state == "kyc_verified"
        tracker.advance(db, order, "admin")
        assert order.state == "engineer_scheduled" and order.engineer_slot is not None
        tracker.advance(db, order, "admin")
        tracker.advance(db, order, "admin")
        assert order.state == "activated"
        with pytest.raises(HTTPException):
            tracker.advance(db, order, "admin")
        db.commit()
        notes = db.scalars(select(Notification).where(Notification.order_id == order_id)).all()
        # placed + kyc + hold + resume + scheduled + installed + activated
        assert len(notes) == 7
        assert all(n.to_masked == "XXXXXX3210" for n in notes)
        assert all(f"/track/{order_id}?t=" in n.body for n in notes)
    finally:
        gen.close()

    view = client.get(f"/api/v1/orders/{order_id}", headers=h).json()
    assert all(s["done"] for s in view["steps"])
    assert view["slot_options"] == []


def test_cannot_skip_states(client):
    from app.services import tracker

    order_id, _ = placed_order(client)
    gen, db = _db()
    try:
        order = db.get(Order, order_id)
        with pytest.raises(HTTPException):
            tracker.set_state(db, order, "installed", "admin")
        with pytest.raises(HTTPException):
            tracker.set_state(db, order, "on_hold", "admin")  # hold needs a reason
    finally:
        gen.close()
