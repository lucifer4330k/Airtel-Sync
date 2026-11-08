"""Shared request dependencies: owner capability token."""

from typing import Annotated

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.core.security import verify_kyc_token
from app.models import Business


def owner_token(
    x_owner_token: Annotated[str | None, Header()] = None,
    x_kyc_token: Annotated[str | None, Header()] = None,
) -> str | None:
    """X-Owner-Token (X-KYC-Token accepted for older clients)."""
    return x_owner_token or x_kyc_token


def require_owner(db: Session, business_id: int, token: str | None) -> Business:
    # Same 404 for "no such business" and "wrong token", so ids can't be probed.
    biz = db.get(Business, business_id)
    if biz is None or not verify_kyc_token(business_id, token):
        raise HTTPException(404, "Not found")
    return biz
