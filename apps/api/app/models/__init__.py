"""The 13 tables of the owner journey. Every row that touches a person carries
a purpose (via consents) and a retention date (purge_after on documents)."""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import EncryptedString
from app.db import Base


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30))
    price_min: Mapped[int] = mapped_column(Integer)
    price_max: Mapped[int] = mapped_column(Integer)
    setup_fee: Mapped[int] = mapped_column(Integer)
    min_contract_months: Mapped[int] = mapped_column(Integer)
    tiers: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    min_employees: Mapped[int] = mapped_column(Integer)
    min_sites: Mapped[int] = mapped_column(Integer)
    requires_gstin: Mapped[bool] = mapped_column(Boolean)
    requires_one_of: Mapped[list[str]] = mapped_column(ARRAY(String(4)))
    install_days: Mapped[int] = mapped_column(Integer)
    segments: Mapped[list[str]] = mapped_column(ARRAY(String(10)))


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    # name / type / city / state are filled from the registry lookup, so a
    # business created at the consent step starts without them.
    name: Mapped[str | None] = mapped_column(String(200))
    type: Mapped[str | None] = mapped_column(String(80))
    segment: Mapped[str] = mapped_column(String(10))  # micro / prof / multi / mfg
    city: Mapped[str | None] = mapped_column(String(80))
    tier: Mapped[int] = mapped_column(Integer)
    state: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str | None] = mapped_column(String(30))
    employees: Mapped[int] = mapped_column(Integer)
    sites: Mapped[int] = mapped_column(Integer)
    turnover_band: Mapped[str | None] = mapped_column(String(30))
    gstin: Mapped[str | None] = mapped_column(EncryptedString(255))
    udyam_number: Mapped[str | None] = mapped_column(EncryptedString(255))
    current_internet: Mapped[str | None] = mapped_column(String(40))
    telecom_spend: Mapped[int | None] = mapped_column(Integer)
    # Owner's mobile for order updates (WhatsApp/SMS); encrypted, shown masked.
    phone: Mapped[str | None] = mapped_column(EncryptedString(255))


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(10), unique=True)  # L00001
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    source: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(30))
    outcome: Mapped[str | None] = mapped_column(String(20))
    drop_reason: Mapped[str | None] = mapped_column(String(80))
    products_of_interest: Mapped[list[str]] = mapped_column(ARRAY(String(4)), default=list)
    assigned_to: Mapped[str | None] = mapped_column(String(80))
    propensity_score: Mapped[float | None] = mapped_column(Float)
    score_reasons: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    # Where the digital journey stopped and why, for the partner console.
    stopped_at: Mapped[str | None] = mapped_column(String(30))  # advisor / quote / checkout / kyc
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    needs_human_reason: Mapped[str | None] = mapped_column(Text)
    suggested_bundle: Mapped[dict | None] = mapped_column(JSON)
    follow_ups: Mapped[list | None] = mapped_column(JSON)  # [{at, by, note}]


class AdvisorSession(Base):
    __tablename__ = "advisor_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"))
    channel: Mapped[str] = mapped_column(String(10))  # web / whatsapp / voice
    language: Mapped[str] = mapped_column(String(30))
    slots: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open")


class AdvisorMessage(Base):
    __tablename__ = "advisor_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("advisor_sessions.id"))
    role: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)  # PII-masked before insert
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"))
    tier: Mapped[str] = mapped_column(String(10))  # good / better / best
    monthly_total: Mapped[int] = mapped_column(Integer)
    setup_total: Mapped[int] = mapped_column(Integer)
    contract_months: Mapped[int] = mapped_column(Integer)
    eta_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / accepted / superseded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)
    is_addon: Mapped[bool] = mapped_column(Boolean, default=False)


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    purpose: Mapped[str] = mapped_column(String(30))  # kyc / marketing
    text_version: Mapped[str] = mapped_column(String(20))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    doc_type: Mapped[str] = mapped_column(String(30))
    storage_key: Mapped[str | None] = mapped_column(String(255))  # null once purged
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    purge_after: Mapped[date | None] = mapped_column(Date)


class KycCheck(Base):
    __tablename__ = "kyc_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kyc_documents.id", ondelete="CASCADE"))
    check_name: Mapped[str] = mapped_column(String(60))
    result: Mapped[str] = mapped_column(String(10))  # pass / fail / review
    reason: Mapped[str] = mapped_column(Text)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"))
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    state: Mapped[str] = mapped_column(String(30), default="order_placed")
    hold_reason: Mapped[str | None] = mapped_column(Text)
    eta_date: Mapped[date | None] = mapped_column(Date)
    engineer_slot: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_method: Mapped[str | None] = mapped_column(String(30))  # upi_autopay / razorpay
    payment_ref: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    event: Mapped[str] = mapped_column(String(80))  # e.g. console.view_pii
    target: Mapped[str | None] = mapped_column(String(80))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """Outbox for WhatsApp / SMS. Sent via sandbox when configured, else mocked."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(10))  # whatsapp / sms
    to_masked: Mapped[str | None] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued / sent / mocked / failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsoleUser(Base):
    """Back-office accounts: rep, partner, admin. Territory = city they cover."""

    __tablename__ = "console_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(10))  # rep / partner / admin
    city: Mapped[str | None] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
