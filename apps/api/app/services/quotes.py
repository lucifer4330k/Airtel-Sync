"""Persisted quotes: Good / Better / Best per lead, add-on toggles, re-pricing.

Every change goes back through the rules engine, so a quote can never hold an
ineligible product or a product whose required connection was removed.
"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import quote_share_token
from app.models import Business, Lead, Quote, QuoteItem
from app.services.catalogue import get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import TEMPLATES, build_tiers, price_bundle, quantity_for
from app.services.registry import gstin_is_active


def profile_of(biz: Business) -> BusinessProfile:
    return BusinessProfile(
        segment=biz.segment,
        city_tier=biz.tier,
        employees=biz.employees,
        sites=biz.sites,
        gstin_active=gstin_is_active(biz.gstin),
    )


def _write_items(
    db: Session, quote: Quote, quantities: dict[str, int], biz: BusinessProfile, addons: set[str]
):
    priced = price_bundle(quantities, biz, quote.tier, frozenset(addons))
    for old in db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id)):
        db.delete(old)
    db.flush()
    for i in priced.items:
        db.add(
            QuoteItem(
                quote_id=quote.id,
                product_id=i.product_id,
                qty=i.qty,
                unit_price=i.unit_price,
                is_addon=i.is_addon,
            )
        )
    quote.monthly_total = priced.monthly_total
    quote.setup_total = priced.setup_total
    quote.contract_months = priced.contract_months
    quote.eta_days = priced.eta_days


def create_quotes(db: Session, lead: Lead, biz: Business) -> list[Quote]:
    """Build Good / Better / Best for a lead; older drafts are superseded."""
    for q in db.scalars(select(Quote).where(Quote.lead_id == lead.id, Quote.status == "draft")):
        q.status = "superseded"
    profile = profile_of(biz)
    quotes = []
    for bundle in build_tiers(profile):
        q = Quote(
            lead_id=lead.id, tier=bundle.tier, monthly_total=0, setup_total=0, contract_months=0, eta_days=0
        )
        db.add(q)
        db.flush()
        _write_items(db, q, {i.product_id: i.qty for i in bundle.items}, profile, set())
        quotes.append(q)
    lead.suggested_bundle = {
        "tiers": [q.tier for q in quotes],
        "recommended": next((q.id for q in quotes if q.tier == "better"), quotes[0].id if quotes else None),
    }
    lead.stopped_at = "quote"
    return quotes


def _items(db: Session, quote: Quote) -> list[QuoteItem]:
    return list(db.scalars(select(QuoteItem).where(QuoteItem.quote_id == quote.id).order_by(QuoteItem.id)))


def addon_options(quote_items: list[QuoteItem], biz: Business) -> list[dict]:
    """Products the owner could toggle on or off, each with a one-line reason when blocked."""
    catalogue = get_catalogue()
    profile = profile_of(biz)
    in_quote = {i.product_id for i in quote_items}
    relevant = {pid for tier in TEMPLATES[biz.segment].values() for slot in tier for pid in slot}
    relevant |= {p.product_id for p in catalogue.values() if biz.segment in p.segments}
    options = []
    # One primary connection per plan: other primary options are swapped by
    # choosing another tier, not stacked as add-ons.
    primary = {"P01", "P02", "P03", "P04", "P05", "P06"}
    if in_quote & primary:
        relevant -= primary - in_quote
    for pid in sorted(relevant):
        p = catalogue[pid]
        included = pid in in_quote
        if included:
            remaining = in_quote - {pid}
            broken = validate_bundle(remaining).violations
            reason = (
                f"{catalogue[broken[0].product_id].name} needs this connection. Remove that first."
                if broken
                else None
            )
        else:
            elig = eligible(p, profile)
            if not elig.ok:
                reason = elig.reasons[0]
            else:
                deps = validate_bundle(in_quote | {pid}).violations
                reason = deps[0].message if deps else None
        qty = quantity_for(p, profile)
        options.append(
            {
                "product_id": pid,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "included": included,
                "qty": qty,
                "monthly_from": p.price_min * qty,
                "available": reason is None,
                "reason": reason,
            }
        )
    return options


def toggle(db: Session, quote: Quote, biz: Business, product_id: str, include: bool) -> Quote:
    if quote.status != "draft":
        raise HTTPException(409, "This quote can no longer be changed")
    catalogue = get_catalogue()
    if product_id not in catalogue:
        raise HTTPException(422, f"Unknown product {product_id}")
    items = _items(db, quote)
    quantities = {i.product_id: i.qty for i in items}
    addons = {i.product_id for i in items if i.is_addon}
    profile = profile_of(biz)
    p = catalogue[product_id]

    if include:
        if product_id in quantities:
            return quote
        elig = eligible(p, profile)
        if not elig.ok:
            raise HTTPException(422, elig.reasons[0])
        quantities[product_id] = quantity_for(p, profile)
        addons.add(product_id)
    else:
        if product_id not in quantities:
            return quote
        quantities.pop(product_id)
        addons.discard(product_id)

    check = validate_bundle(quantities.keys())
    if not check.ok:
        v = check.violations[0]
        if include:
            raise HTTPException(422, v.message)
        raise HTTPException(422, f"{catalogue[v.product_id].name} needs this connection. Remove that first.")
    if not quantities:
        raise HTTPException(422, "A quote needs at least one service")
    _write_items(db, quote, quantities, profile, addons)
    return quote


def view(db: Session, quote: Quote, biz: Business, *, with_options: bool = True) -> dict:
    catalogue = get_catalogue()
    items = _items(db, quote)
    eta_date = get_settings().reference_date + timedelta(days=quote.eta_days)
    return {
        "id": quote.id,
        "tier": quote.tier,
        "status": quote.status,
        "business_id": biz.id,
        "items": [
            {
                "product_id": i.product_id,
                "name": catalogue[i.product_id].name,
                "description": catalogue[i.product_id].description,
                "unit": catalogue[i.product_id].unit,
                "qty": i.qty,
                "unit_price": i.unit_price,
                "monthly": i.unit_price * i.qty,
                "setup": catalogue[i.product_id].setup_fee * i.qty,
                "install_days": catalogue[i.product_id].install_days,
                "is_addon": i.is_addon,
            }
            for i in items
        ],
        "monthly_total": quote.monthly_total,
        "setup_total": quote.setup_total,
        "contract_months": quote.contract_months,
        "eta_days": quote.eta_days,
        "eta_date": eta_date,
        "share_token": quote_share_token(quote.id),
        "siblings": [
            q.id
            for q in db.scalars(
                select(Quote)
                .where(Quote.lead_id == quote.lead_id, Quote.status != "superseded")
                .order_by(Quote.id)
            )
        ]
        if with_options
        else [quote.id],
        "addons": addon_options(items, biz) if with_options and quote.status == "draft" else [],
    }
