"""Seeding: catalogue products, the 5,000 historical leads, console accounts
and a demo owner with a placed order.

Used by scripts/seed_db.py (manual, wipes first) and app.bootstrap (first
boot on an empty database). Inserts are batched so seeding a hosted database
takes seconds, not minutes.
"""

import csv
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, kyc_token
from app.models import (
    AdvisorMessage,
    AdvisorSession,
    AuditLog,
    Business,
    Consent,
    ConsoleUser,
    KycCheck,
    KycDocument,
    Lead,
    Notification,
    Order,
    OrderEvent,
    Product,
    Quote,
    QuoteItem,
)
from app.services.catalogue import SEGMENT_CODES, get_catalogue

# Where each historical lead's journey stopped, for the console.
STOPPED_AT = {
    "Lead": "advisor",
    "Contacted": "advisor",
    "Needs assessed": "quote",
    "Quote accepted": "kyc",
    "KYC complete": "install",
    "Activated": None,
}
TEAM = [
    ("admin", "Asha Admin", "admin", None),
    ("rep.pune", "Rohan (Field rep, Pune)", "rep", "Pune"),
    ("partner.mumbai", "Mehta Telecom (Partner, Mumbai)", "partner", "Mumbai"),
    ("partner.delhi", "Capital Connect (Partner, Delhi)", "partner", "Delhi"),
]


def seed_products(db: Session) -> int:
    """Upsert the 25 catalogue products. Idempotent."""
    existing = {p.product_id: p for p in db.scalars(select(Product))}
    for p in get_catalogue().values():
        row = existing.get(p.product_id) or Product(product_id=p.product_id)
        row.name, row.category, row.description, row.unit = p.name, p.category, p.description, p.unit
        row.price_min, row.price_max, row.setup_fee = p.price_min, p.price_max, p.setup_fee
        row.min_contract_months, row.tiers = p.min_contract_months, list(p.tiers)
        row.min_employees, row.min_sites, row.requires_gstin = p.min_employees, p.min_sites, p.requires_gstin
        row.requires_one_of, row.install_days = list(p.requires_one_of), p.install_days
        row.segments = list(p.segments)
        db.add(row)
    db.flush()
    return len(get_catalogue())


def wipe(db: Session) -> None:
    for model in (
        Notification, OrderEvent, Order, KycCheck, KycDocument, Consent, QuoteItem, Quote,
        AdvisorMessage, AdvisorSession, Lead, Business, ConsoleUser, AuditLog,
    ):  # fmt: skip
        db.execute(delete(model))


def seed_leads(db: Session) -> int:
    from app.services.propensity import lead_features, score

    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    businesses = [
        Business(
            name=r["business_name"],
            type=r["business_type"],
            segment=SEGMENT_CODES[r["segment"]],
            city=r["city"],
            tier=int(r["city_tier"]),
            state=r["state"],
            language=r["preferred_language"],
            employees=int(r["employee_count"]),
            sites=int(r["num_sites"]),
            turnover_band=r["annual_turnover_band"],
            gstin=r["gstin"] or None,
            udyam_number=r["udyam_number"] or None,
            current_internet=r["current_internet"],
            telecom_spend=int(r["monthly_telecom_spend_inr"] or 0),
        )
        for r in rows
    ]
    db.add_all(businesses)
    db.flush()  # one batched INSERT ... RETURNING for all ids

    leads = []
    for r, biz in zip(rows, businesses, strict=True):
        products = [p for p in r["products_of_interest"].split(";") if p]
        scored = score(
            lead_features(
                segment=biz.segment,
                business_type=biz.type,
                source=r["lead_source"],
                city_tier=biz.tier,
                language=biz.language,
                turnover_band=biz.turnover_band,
                current_internet=biz.current_internet,
                employees=biz.employees,
                sites=biz.sites,
                telecom_spend=biz.telecom_spend,
                products=products,
                gstin=r["gstin"] or None,
                has_udyam=r["has_udyam"] == "Y",
            )
        )
        leads.append(
            Lead(
                external_id=r["lead_id"],
                business_id=biz.id,
                source=r["lead_source"],
                stage=r["stage_reached"],
                outcome=r["outcome"] or None,
                drop_reason=r["drop_reason"] or None,
                products_of_interest=products,
                created_at=date.fromisoformat(r["created_date"]),
                stopped_at=STOPPED_AT[r["stage_reached"]],
                propensity_score=scored[0] if scored else None,
                score_reasons=scored[1] if scored else None,
            )
        )
    db.add_all(leads)
    db.flush()
    return len(rows)


def seed_team(db: Session, password: str) -> None:
    for username, name, role, city in TEAM:
        db.add(
            ConsoleUser(
                username=username, name=name, role=role, city=city, password_hash=hash_password(password)
            )
        )
    db.flush()


def seed_demo_owner(db: Session) -> dict:
    """A Pune clinic with a placed order, so the tracker can be shown at once."""
    from app.services import quotes as quote_svc
    from app.services import tracker
    from app.services.leads import upsert

    demo, lead = upsert(
        db, segment="prof", city_tier=1, employees=8, sites=1, city="Pune", business_type="Dental clinic",
        phone="9876543210", language="en",
    )  # fmt: skip
    demo.name = "Demo Smile Dental Clinic"
    lead.source = "Website form"
    quotes = quote_svc.create_quotes(db, lead, demo)
    chosen = next(q for q in quotes if q.tier == "better")
    chosen.status = "accepted"
    order = tracker.create_order(db, chosen, demo.id, "upi_autopay", "mdt_test_demo")
    lead.stage = "Quote accepted"
    db.flush()
    token = kyc_token(demo.id)
    web = get_settings().public_web_url
    return {
        "tracker": f"{web}/track/{order.id}?t={token}",
        "plan": f"{web}/resume?b={demo.id}&t={token}&q={chosen.id}",
    }


def seed_all(db: Session, password: str, *, wipe_first: bool) -> dict:
    if wipe_first:
        wipe(db)
    seed_products(db)
    n = seed_leads(db)
    seed_team(db, password)
    links = seed_demo_owner(db)
    return {"leads": n, **links}
