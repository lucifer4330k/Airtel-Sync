"""Creating and updating the business + lead behind every digital journey."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, Lead
from app.services.registry import lookup_gstin

SOURCE_BY_CHANNEL = {"web": "Website form", "whatsapp": "WhatsApp campaign", "voice": "Website form"}


def lead_for_business(db: Session, business_id: int) -> Lead | None:
    return db.scalar(select(Lead).where(Lead.business_id == business_id).order_by(Lead.id.desc()))


def upsert(
    db: Session,
    *,
    segment: str,
    city_tier: int,
    employees: int,
    sites: int,
    business: Business | None = None,
    gstin: str | None = None,
    phone: str | None = None,
    business_type: str | None = None,
    city: str | None = None,
    language: str | None = None,
    current_internet: str | None = None,
    telecom_spend: int | None = None,
    products_of_interest: list[str] | None = None,
    channel: str = "web",
) -> tuple[Business, Lead]:
    biz = business or Business(segment=segment, tier=city_tier, employees=employees, sites=sites)
    biz.segment, biz.tier, biz.employees, biz.sites = segment, city_tier, employees, sites
    for attr, value in {
        "type": business_type,
        "city": city,
        "language": language,
        "current_internet": current_internet,
        "telecom_spend": telecom_spend,
        "phone": phone,
    }.items():
        if value is not None:
            setattr(biz, attr, value)
    if gstin:
        biz.gstin = gstin.strip().upper()
        if rec := lookup_gstin(biz.gstin):
            biz.name = biz.name or rec["legal_name"]
            biz.state = biz.state or rec["state"]
    if business is None:
        db.add(biz)
    db.flush()

    lead = lead_for_business(db, biz.id)
    if lead is None:
        lead = Lead(
            business_id=biz.id,
            source=SOURCE_BY_CHANNEL.get(channel, "Website form"),
            stage="Needs assessed",
            products_of_interest=products_of_interest or [],
            stopped_at="advisor",
        )
        db.add(lead)
        db.flush()
    elif products_of_interest:
        lead.products_of_interest = sorted(set(lead.products_of_interest or []) | set(products_of_interest))
    from app.services.propensity import score_lead

    score_lead(db, lead)
    return biz, lead
