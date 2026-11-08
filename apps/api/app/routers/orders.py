"""Owner-facing order tracker."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import owner_token, require_owner
from app.db import get_db
from app.models import Order
from app.services import tracker

router = APIRouter(prefix="/orders", tags=["orders"])
Db = Annotated[Session, Depends(get_db)]
Token = Annotated[str | None, Depends(owner_token)]


class RescheduleIn(BaseModel):
    start: str = Field(max_length=40, description="One of slot_options[].start")


def _order(db: Session, order_id: int, token: str | None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Not found")
    require_owner(db, order.business_id, token)
    return order


@router.get("")
def my_orders(business_id: int, db: Db, token: Token):
    require_owner(db, business_id, token)
    orders = db.scalars(select(Order).where(Order.business_id == business_id).order_by(Order.id.desc()))
    return [tracker.view(db, o) for o in orders]


@router.get("/{order_id}")
def get_order(order_id: int, db: Db, token: Token):
    return tracker.view(db, _order(db, order_id, token))


@router.post("/{order_id}/reschedule")
def reschedule(order_id: int, body: RescheduleIn, db: Db, token: Token):
    order = tracker.reschedule(db, _order(db, order_id, token), body.start)
    db.commit()
    return tracker.view(db, order)
