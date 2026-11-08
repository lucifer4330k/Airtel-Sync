"""Quotes and checkout.

POST /quotes          build Good / Better / Best for a profile (creates business + lead)
GET  /quotes/{id}     view (owner token, or the quote's share token)
PATCH /quotes/{id}/items  toggle an add-on; re-validates and re-prices
POST /quotes/{id}/accept  checkout: mocked UPI AutoPay / Razorpay test payment -> order
POST /quotes/preview  stateless preview (no DB)
POST /quotes/price    stateless price of any bundle
"""

import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import owner_token, require_owner
from app.core.security import kyc_token, verify_kyc_token, verify_scoped_token
from app.db import get_db
from app.models import Business, Lead, Quote
from app.services import leads as lead_svc
from app.services import quotes as quote_svc
from app.services import tracker
from app.services.catalogue import SEGMENT_CODES, get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import build_tiers, price_bundle
from app.services.registry import gstin_is_active

router = APIRouter(prefix="/quotes", tags=["quotes"])
Db = Annotated[Session, Depends(get_db)]
Token = Annotated[str | None, Depends(owner_token)]

PHONE = r"^(\+91)?[6-9]\d{9}$"


class ProfileIn(BaseModel):
    segment: str = Field(description="micro / prof / multi / mfg, or the lead-data segment name")
    city_tier: int = Field(ge=1, le=2)
    employees: int = Field(ge=1, le=10000)
    sites: int = Field(ge=1, le=500)
    gstin: str | None = Field(None, max_length=15)

    def segment_code(self) -> str:
        seg = SEGMENT_CODES.get(self.segment, self.segment)
        if seg not in {"micro", "prof", "multi", "mfg"}:
            raise HTTPException(422, f"Unknown segment '{self.segment}'")
        return seg

    def to_profile(self) -> BusinessProfile:
        return BusinessProfile(
            segment=self.segment_code(),
            city_tier=self.city_tier,
            employees=self.employees,
            sites=self.sites,
            gstin_active=gstin_is_active(self.gstin),
        )


class CustomBundleIn(BaseModel):
    profile: ProfileIn
    items: dict[str, int] = Field(description="product_id -> quantity")


class CreateQuotesIn(BaseModel):
    profile: ProfileIn
    business_id: int | None = None  # re-quote an existing business (owner token required)
    language: str | None = None
    channel: Literal["web", "whatsapp", "voice"] = "web"


class ToggleIn(BaseModel):
    product_id: str = Field(max_length=4)
    include: bool


class AcceptIn(BaseModel):
    payment_method: Literal["upi_autopay", "razorpay"] = "upi_autopay"
    phone: str = Field(pattern=PHONE, description="Owner mobile for order updates")
    upi_id: str | None = Field(None, max_length=60, pattern=r"^[\w.\-]{2,}@[a-zA-Z]{2,}$")


# --- stateless -------------------------------------------------------------------


@router.post("/preview")
def preview(profile: ProfileIn):
    biz = profile.to_profile()
    return {"gstin_active": biz.gstin_active, "tiers": build_tiers(biz)}


@router.post("/price")
def price_custom(body: CustomBundleIn):
    """Price an arbitrary bundle, refusing ineligible items and broken dependencies."""
    biz = body.profile.to_profile()
    catalogue = get_catalogue()
    unknown = [pid for pid in body.items if pid not in catalogue]
    if unknown:
        raise HTTPException(422, f"Unknown products: {', '.join(unknown)}")
    problems = [r for pid in body.items for r in eligible(catalogue[pid], biz).reasons]
    problems += [v.message for v in validate_bundle(body.items.keys()).violations]
    if problems:
        raise HTTPException(422, {"reasons": problems})
    return price_bundle(body.items, biz)


# --- persisted -------------------------------------------------------------------


def _quote_and_business(db: Session, quote_id: int) -> tuple[Quote, Business, Lead]:
    quote = db.get(Quote, quote_id)
    lead = quote and db.get(Lead, quote.lead_id)
    biz = lead and db.get(Business, lead.business_id)
    if not (quote and lead and biz):
        raise HTTPException(404, "Not found")
    return quote, biz, lead


@router.post("", status_code=201)
def create(body: CreateQuotesIn, db: Db, token: Token):
    p = body.profile
    existing = require_owner(db, body.business_id, token) if body.business_id else None
    biz, lead = lead_svc.upsert(
        db,
        business=existing,
        segment=p.segment_code(),
        city_tier=p.city_tier,
        employees=p.employees,
        sites=p.sites,
        gstin=p.gstin,
        language=body.language,
        channel=body.channel,
    )
    quotes = quote_svc.create_quotes(db, lead, biz)
    if not quotes:
        raise HTTPException(422, "No plan fits this business yet; a specialist will call you")
    db.commit()
    return {
        "business_id": biz.id,
        "owner_token": kyc_token(biz.id),
        "gstin_active": gstin_is_active(biz.gstin),
        "recommended": lead.suggested_bundle["recommended"],
        "quotes": [quote_svc.view(db, q, biz) for q in quotes],
    }


@router.get("/{quote_id}")
def get_quote(quote_id: int, db: Db, token: Token, share: Annotated[str | None, Query(max_length=64)] = None):
    quote, biz, _ = _quote_and_business(db, quote_id)
    is_owner = verify_kyc_token(biz.id, token)
    if not (is_owner or verify_scoped_token("quote", quote_id, share)):
        raise HTTPException(404, "Not found")
    return quote_svc.view(db, quote, biz, with_options=is_owner)


@router.patch("/{quote_id}/items")
def toggle_item(quote_id: int, body: ToggleIn, db: Db, token: Token):
    quote, biz, _ = _quote_and_business(db, quote_id)
    require_owner(db, biz.id, token)
    quote_svc.toggle(db, quote, biz, body.product_id, body.include)
    db.commit()
    return quote_svc.view(db, quote, biz)


@router.post("/{quote_id}/accept", status_code=201)
def accept(quote_id: int, body: AcceptIn, db: Db, token: Token):
    """Checkout. Payment is mocked in the shape of a Razorpay test order or a
    UPI AutoPay mandate; real integrations need business onboarding."""
    quote, biz, lead = _quote_and_business(db, quote_id)
    require_owner(db, biz.id, token)
    if quote.status != "draft":
        raise HTTPException(409, "This quote was already accepted or replaced")

    # Re-validate one last time: eligibility can change (e.g. GST cancelled).
    profile = quote_svc.profile_of(biz)
    items = quote_svc._items(db, quote)
    catalogue = get_catalogue()
    bad = [r for i in items for r in eligible(catalogue[i.product_id], profile).reasons]
    bad += [v.message for v in validate_bundle([i.product_id for i in items]).violations]
    if bad:
        raise HTTPException(422, {"reasons": bad})

    for other in db.scalars(select(Quote).where(Quote.lead_id == lead.id, Quote.id != quote.id)):
        if other.status == "draft":
            other.status = "superseded"
    quote.status = "accepted"
    biz.phone = body.phone[-10:]
    prefix = "mdt_test_" if body.payment_method == "upi_autopay" else "pay_test_"
    payment_ref = prefix + secrets.token_hex(7)
    order = tracker.create_order(db, quote, biz.id, body.payment_method, payment_ref)
    lead.stage, lead.stopped_at = "Quote accepted", "kyc"
    db.commit()
    return {"order_id": order.id, "payment_ref": payment_ref, "owner_token": kyc_token(biz.id)}


# --- what-if: repair a quote when the budget or needs change -------------------------


class WhatIfIn(BaseModel):
    budget: int | None = Field(None, ge=100, le=10_000_000)
    must_have: list[str] = Field(default_factory=list, max_length=25)
    add: list[str] = Field(default_factory=list, max_length=25)
    remove: list[str] = Field(default_factory=list, max_length=25)
    sites: int | None = Field(None, ge=1, le=500)
    city_tier: Literal[1, 2] | None = None
    # Only "I no longer have GST" is a what-if; gaining GST needs a verified GSTIN.
    gstin_active: Literal[False] | None = None
    connection: str | None = Field(None, max_length=4)

    def request(self):
        from app.services.repair import ChangeRequest

        return ChangeRequest(
            budget=self.budget,
            must_have=frozenset(self.must_have),
            add=frozenset(self.add),
            remove=frozenset(self.remove),
            sites=self.sites,
            city_tier=self.city_tier,
            gstin_active=self.gstin_active,
            connection=self.connection,
        )


class ApplyIn(WhatIfIn):
    option_id: str = Field(max_length=30)


def _what_if(db: Session, quote_id: int, body: WhatIfIn, token: str | None):
    from app.services.repair import analyse

    quote, biz, lead = _quote_and_business(db, quote_id)
    require_owner(db, biz.id, token)
    if quote.status != "draft":
        raise HTTPException(409, "This quote can no longer be changed")
    current = {i.product_id: i.qty for i in quote_svc._items(db, quote)}
    try:
        result = analyse(current, quote_svc.profile_of(biz), body.request())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return quote, biz, lead, result


@router.post("/{quote_id}/what-if")
def what_if(quote_id: int, body: WhatIfIn, db: Db, token: Token):
    """Explain what breaks and offer the smallest valid fix. Changes nothing."""
    quote, _, _, result = _what_if(db, quote_id, body, token)
    return {"current_total": quote.monthly_total, **result.as_dict()}


@router.post("/{quote_id}/what-if/apply")
def apply_what_if(quote_id: int, body: ApplyIn, db: Db, token: Token):
    from app.core.logging import mask_pii
    from app.services.catalogue import get_catalogue as cat

    quote, biz, lead, result = _what_if(db, quote_id, body, token)
    option = next((o for o in result.options if o.id == body.option_id), None)
    if option is None:
        raise HTTPException(422, "That option is no longer available; check again")
    if option.kind == "handoff":
        needs = ", ".join(cat()[p].name for p in option.unmet) or "site assessment"
        lead.needs_human = True
        lead.needs_human_reason = mask_pii(
            f"Site assessment requested from the quote. Keep these needs: {needs}. "
            f"Last quote #{quote.id}, {quote.monthly_total}/month."
        )
        lead.stopped_at = "quote"
        db.commit()
        return {
            "handoff": True,
            "message": "A specialist will call you to assess the site. Your needs are saved.",
        }
    if body.sites:
        biz.sites = body.sites
    if body.city_tier:
        biz.tier = body.city_tier
    profile = quote_svc.profile_of(biz)
    if body.gstin_active is False:
        from dataclasses import replace as _replace

        profile = _replace(profile, gstin_active=False)
    quote_svc._write_items(db, quote, option.items, profile, set(body.add) & set(option.items))
    db.commit()
    return quote_svc.view(db, quote, biz)
