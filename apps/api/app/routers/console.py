"""Partner and field console.

Roles: admin (everything), rep and partner (their city's leads, plus leads
assigned to them). Every view of a person's details writes an audit row.
"""

import csv
import statistics
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import mask_pii, redact_tokens
from app.core.ratelimit import limit
from app.core.security import console_jwt, decode_console_jwt, verify_password
from app.db import get_db
from app.models import (
    AdvisorMessage,
    AdvisorSession,
    AuditLog,
    Business,
    ConsoleUser,
    KycCheck,
    KycDocument,
    Lead,
    Notification,
    Order,
    Quote,
)
from app.services import tracker
from app.services.catalogue import SEGMENT_CODES
from app.services.kyc.case import case_status, process_case

router = APIRouter(prefix="/console", tags=["console"])
Db = Annotated[Session, Depends(get_db)]
STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
SEGMENT_LABEL = {v: k for k, v in SEGMENT_CODES.items()}


class Me(BaseModel):
    id: int
    username: str
    role: str
    city: str | None


def current_user(authorization: Annotated[str | None, Header()] = None) -> Me:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in to the console")
    claims = decode_console_jwt(authorization.split(" ", 1)[1])
    if not claims:
        raise HTTPException(401, "Session expired. Sign in again.")
    return Me(id=int(claims["sub"]), username=claims["usr"], role=claims["role"], city=claims.get("city"))


User = Annotated[Me, Depends(current_user)]


def admin_only(user: User) -> Me:
    if user.role != "admin":
        raise HTTPException(403, "Admins only")
    return user


def _audit(db: Session, user: Me, event: str, target: str) -> None:
    db.add(AuditLog(actor=f"{user.role}:{user.username}", event=event, target=target))


def _scope(stmt, user: Me):
    """Reps and partners see their own city plus anything assigned to them."""
    if user.role == "admin":
        return stmt
    return stmt.where(or_(Business.city == user.city, Lead.assigned_to == user.username))


# --- auth -------------------------------------------------------------------------


class LoginIn(BaseModel):
    username: str = Field(max_length=60)
    password: str = Field(max_length=200)


@router.post("/login", dependencies=[Depends(limit(10, 60))])
def login(body: LoginIn, db: Db):
    user = db.scalar(select(ConsoleUser).where(ConsoleUser.username == body.username.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return {
        "token": console_jwt(user.id, user.username, user.role, user.city),
        "user": {"username": user.username, "name": user.name, "role": user.role, "city": user.city},
    }


@router.get("/me")
def me(user: User):
    return user


@router.get("/team")
def team(user: User, db: Db):
    rows = db.scalars(select(ConsoleUser).order_by(ConsoleUser.role, ConsoleUser.name))
    return [{"username": u.username, "name": u.name, "role": u.role, "city": u.city} for u in rows]


# --- leads -----------------------------------------------------------------------


def _lead_row(lead: Lead, biz: Business) -> dict:
    return {
        "id": lead.id,
        "external_id": lead.external_id,
        "business": biz.name or f"{biz.type or 'Business'} #{biz.id}",
        "type": biz.type,
        "segment": SEGMENT_LABEL.get(biz.segment, biz.segment),
        "city": biz.city,
        "tier": biz.tier,
        "employees": biz.employees,
        "sites": biz.sites,
        "source": lead.source,
        "stage": lead.stage,
        "outcome": lead.outcome,
        "stopped_at": lead.stopped_at,
        "drop_reason": lead.drop_reason,
        "needs_human": lead.needs_human,
        "needs_human_reason": lead.needs_human_reason,
        "products_of_interest": lead.products_of_interest,
        "score": lead.propensity_score,
        "reasons": lead.score_reasons or [],
        "assigned_to": lead.assigned_to,
        "created_at": lead.created_at,
        "digital": lead.external_id is None,
    }


@router.get("/leads")
def list_leads(
    user: User,
    db: Db,
    view: Literal["open", "needs_human", "digital", "all"] = "open",
    city: str | None = None,
    min_score: float | None = Query(None, ge=0, le=1),
    q: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
):
    stmt = select(Lead, Business).join(Business, Business.id == Lead.business_id)
    stmt = _scope(stmt, user)
    if view == "open":
        stmt = stmt.where(or_(Lead.outcome.is_(None), Lead.outcome != "Activated"), Lead.stage != "Activated")
    elif view == "needs_human":
        stmt = stmt.where(Lead.needs_human.is_(True))
    elif view == "digital":
        stmt = stmt.where(Lead.external_id.is_(None))
    if city:
        stmt = stmt.where(Business.city == city)
    if min_score is not None:
        stmt = stmt.where(Lead.propensity_score >= min_score)
    if q:
        stmt = stmt.where(
            or_(Business.name.ilike(f"%{q}%"), Business.type.ilike(f"%{q}%"), Lead.external_id == q.upper())
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Lead.needs_human.desc(), Lead.propensity_score.desc().nulls_last(), Lead.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {"total": total, "page": page, "items": [_lead_row(lead, biz) for lead, biz in rows]}


def _lead(db: Session, user: Me, lead_id: int) -> tuple[Lead, Business]:
    row = db.execute(
        _scope(select(Lead, Business).join(Business, Business.id == Lead.business_id), user).where(
            Lead.id == lead_id
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Lead not found")
    return row[0], row[1]


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, user: User, db: Db):
    lead, biz = _lead(db, user, lead_id)
    _audit(db, user, "console.view_lead", f"lead:{lead.id}")
    session = db.scalar(
        select(AdvisorSession).where(AdvisorSession.lead_id == lead.id).order_by(AdvisorSession.id.desc())
    )
    transcript = []
    if session:
        transcript = [
            {"role": m.role, "text": m.text, "at": m.created_at}
            for m in db.scalars(
                select(AdvisorMessage)
                .where(AdvisorMessage.session_id == session.id)
                .order_by(AdvisorMessage.id)
            )
        ]
    quotes = [
        {
            "id": q.id,
            "tier": q.tier,
            "status": q.status,
            "monthly_total": q.monthly_total,
            "setup_total": q.setup_total,
        }
        for q in db.scalars(select(Quote).where(Quote.lead_id == lead.id).order_by(Quote.id))
    ]
    orders = [tracker.view(db, o) for o in db.scalars(select(Order).where(Order.business_id == biz.id))]
    kyc = (
        case_status(db, biz)
        if db.scalar(select(KycDocument.id).where(KycDocument.business_id == biz.id))
        else None
    )
    db.commit()
    return {
        **_lead_row(lead, biz),
        "phone": mask_pii(biz.phone) if biz.phone else None,
        "gstin": mask_pii(biz.gstin) if biz.gstin else None,
        "language": biz.language,
        "current_internet": biz.current_internet,
        "telecom_spend": biz.telecom_spend,
        "follow_ups": lead.follow_ups or [],
        "transcript": transcript,
        "quotes": quotes,
        "orders": orders,
        "kyc": kyc and {"overall": kyc["overall"], "reasons": kyc["reasons"], "missing": kyc["missing"]},
    }


class AssignIn(BaseModel):
    username: str = Field(max_length=60)


@router.post("/leads/{lead_id}/assign")
def assign(lead_id: int, body: AssignIn, user: User, db: Db):
    lead, biz = _lead(db, user, lead_id)
    target = db.scalar(select(ConsoleUser).where(ConsoleUser.username == body.username))
    if target is None:
        raise HTTPException(422, "No such team member")
    if user.role != "admin" and target.username != user.username:
        raise HTTPException(403, "You can only assign leads to yourself")
    if target.role != "admin" and target.city and biz.city and target.city != biz.city:
        raise HTTPException(422, f"{target.name} covers {target.city}, not {biz.city}")
    lead.assigned_to = target.username
    lead.follow_ups = [
        *(lead.follow_ups or []),
        {"at": datetime.now(UTC).isoformat(), "by": user.username, "note": f"Assigned to {target.name}"},
    ]
    _audit(db, user, "console.assign", f"lead:{lead.id}->{target.username}")
    db.commit()
    return _lead_row(lead, biz)


class FollowUpIn(BaseModel):
    note: str = Field(min_length=2, max_length=500)
    outcome: Literal["called", "visit_booked", "not_reachable", "not_interested", "won"] | None = None


@router.post("/leads/{lead_id}/follow-ups")
def follow_up(lead_id: int, body: FollowUpIn, user: User, db: Db):
    lead, biz = _lead(db, user, lead_id)
    entry = {
        "at": datetime.now(UTC).isoformat(),
        "by": user.username,
        "note": mask_pii(body.note),
        "outcome": body.outcome,
    }
    lead.follow_ups = [*(lead.follow_ups or []), entry]
    if body.outcome == "not_interested":
        lead.outcome, lead.drop_reason = "Dropped", "Not interested (console)"
    if body.outcome in ("called", "visit_booked") and lead.stage == "Lead":
        lead.stage = "Contacted"
    db.commit()
    return _lead_row(lead, biz)


# --- funnel ------------------------------------------------------------------------


@lru_cache
def _history() -> dict:
    """Apr-Jun 2026 quarter from smb_leads.csv (the baseline the digital journey is measured against)."""
    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    reached = {s: 0 for s in STAGES}
    for r in rows:
        idx = STAGES.index(r["stage_reached"])
        for s in STAGES[: idx + 1]:
            reached[s] += 1
    activated = [r for r in rows if r["outcome"] == "Activated"]
    by_source: dict[str, dict] = {}
    for r in rows:
        d = by_source.setdefault(r["lead_source"], {"leads": 0, "activated": 0, "cost": 0})
        d["leads"] += 1
        d["activated"] += r["outcome"] == "Activated"
        d["cost"] += int(r["acquisition_cost_inr"] or 0)
    return {
        "stages": [{"stage": s, "count": reached[s]} for s in STAGES],
        "conversion": round(len(activated) / len(rows), 4),
        "avg_days_to_activate": round(
            statistics.mean(float(r["days_lead_to_activation"]) for r in activated), 1
        ),
        "avg_follow_up_calls": round(
            statistics.mean(int(r["customer_follow_up_calls"] or 0) for r in activated), 1
        ),
        "cac": round(sum(int(r["acquisition_cost_inr"] or 0) for r in rows) / max(1, len(activated))),
        "by_source": [
            {
                "source": k,
                "leads": v["leads"],
                "conversion": round(v["activated"] / v["leads"], 4),
                "cac": round(v["cost"] / max(1, v["activated"])),
            }
            for k, v in sorted(by_source.items(), key=lambda kv: -kv[1]["leads"])
        ],
        "drop_reasons": _drop_reasons(rows),
    }


def _drop_reasons(rows) -> list[dict]:
    counts: dict[str, int] = {}
    for r in rows:
        if r["drop_reason"]:
            counts[r["drop_reason"]] = counts.get(r["drop_reason"], 0) + 1
    return [{"reason": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])][:8]


@router.get("/funnel")
def funnel(user: User, db: Db):
    digital = select(Lead).where(Lead.external_id.is_(None))
    leads = list(db.scalars(digital))
    live_stage = {s: 0 for s in STAGES}
    for lead in leads:
        if lead.stage in STAGES:
            for s in STAGES[: STAGES.index(lead.stage) + 1]:
                live_stage[s] += 1
    orders = list(db.scalars(select(Order)))
    activated = [o for o in orders if o.state == "activated"]
    # Partner credit: digital closes in their territory.
    credits = []
    for u in db.scalars(select(ConsoleUser).where(ConsoleUser.role.in_(["partner", "rep"]))):
        closes = db.scalar(
            select(func.count())
            .select_from(Order)
            .join(Business, Business.id == Order.business_id)
            .where(Business.city == u.city)
        )
        credits.append(
            {"username": u.username, "name": u.name, "role": u.role, "city": u.city, "digital_orders": closes}
        )
    return {
        "history": _history(),
        "live": {
            "stages": [{"stage": s, "count": live_stage[s]} for s in STAGES],
            "orders": len(orders),
            "activated": len(activated),
            "needs_human": sum(1 for lead in leads if lead.needs_human),
        },
        "credits": credits,
    }


# --- KYC review queue ----------------------------------------------------------------


@router.get("/kyc/queue")
def kyc_queue(user: User, db: Db):
    rows = db.execute(
        _scope(
            select(KycCheck, KycDocument, Business, Lead)
            .join(KycDocument, KycDocument.id == KycCheck.document_id)
            .join(Business, Business.id == KycDocument.business_id)
            .outerjoin(Lead, Lead.business_id == Business.id),
            user,
        )
        .where(KycCheck.result == "review")
        .order_by(KycDocument.uploaded_at)
    ).all()
    return [
        {
            "check_id": c.id,
            "check": c.check_name,
            "reason": c.reason,
            "document_id": d.id,
            "doc_type": d.doc_type,
            "business_id": b.id,
            "business": b.name or f"Business #{b.id}",
            "city": b.city,
            "lead_id": lead.id if lead else None,
            "uploaded_at": d.uploaded_at,
        }
        for c, d, b, lead in rows
    ]


class ResolveIn(BaseModel):
    result: Literal["pass", "fail"]
    note: str = Field(min_length=2, max_length=300)


@router.post("/kyc/checks/{check_id}/resolve")
def resolve_check(check_id: int, body: ResolveIn, user: User, db: Db):
    # Partners are credited for sales in their city, so they don't approve KYC.
    if user.role == "partner":
        raise HTTPException(403, "KYC reviews are decided by a rep or an admin")
    row = db.execute(
        _scope(
            select(KycCheck, KycDocument, Business)
            .join(KycDocument, KycDocument.id == KycCheck.document_id)
            .join(Business, Business.id == KycDocument.business_id)
            .outerjoin(Lead, Lead.business_id == Business.id),
            user,
        ).where(KycCheck.id == check_id)
    ).first()
    if row is None:
        raise HTTPException(404, "Check not found")
    check, doc, biz = row
    # Only what the machine sent for review can be decided by a person: a failed
    # check (e.g. cancelled GSTIN) must never be overridden to pass from here.
    if check.result != "review":
        raise HTTPException(409, "Only checks waiting for review can be resolved")
    overrides = dict((doc.extracted or {}).get("overrides", {}))
    overrides[check.check_name] = {"result": body.result, "by": user.username, "note": mask_pii(body.note)}
    doc.extracted = {**(doc.extracted or {}), "overrides": overrides}
    _audit(db, user, "kyc.resolve", f"kyc_check:{check.id}={body.result}")
    result = process_case(db, biz.id)
    db.commit()
    return {"business_id": biz.id, "overall": result}


# --- orders ---------------------------------------------------------------------------


@router.get("/orders")
def list_orders(user: User, db: Db, state: str | None = None):
    stmt = _scope(
        select(Order, Business)
        .join(Business, Business.id == Order.business_id)
        .outerjoin(Lead, Lead.business_id == Business.id),
        user,
    )
    if state:
        stmt = stmt.where(Order.state == state)
    return [
        {**tracker.view(db, o), "business": b.name or f"Business #{b.id}", "city": b.city}
        for o, b in db.execute(stmt.order_by(Order.id.desc()).limit(100)).all()
    ]


def _order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


@router.post("/orders/{order_id}/advance")
def advance_order(order_id: int, user: Annotated[Me, Depends(admin_only)], db: Db):
    order = tracker.advance(db, _order(db, order_id), actor=user.username)
    if order.state == "activated":
        lead = db.scalar(select(Lead).where(Lead.business_id == order.business_id))
        if lead:
            lead.stage, lead.outcome, lead.stopped_at = "Activated", "Activated", None
    db.commit()
    return tracker.view(db, order)


class HoldIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


@router.post("/orders/{order_id}/hold")
def hold_order(order_id: int, body: HoldIn, user: Annotated[Me, Depends(admin_only)], db: Db):
    order = tracker.set_state(db, _order(db, order_id), "on_hold", user.username, body.reason)
    db.commit()
    return tracker.view(db, order)


# --- outbox & audit ---------------------------------------------------------------------


@router.get("/notifications")
def notifications(user: User, db: Db, order_id: int | None = None):
    """Outbox, scoped like leads. Advisor chat replies (no order) are admin-only.
    Bodies never expose owner capability tokens."""
    if user.role == "admin":
        stmt = select(Notification)
    else:
        stmt = _scope(
            select(Notification)
            .join(Order, Order.id == Notification.order_id)
            .join(Business, Business.id == Order.business_id)
            .outerjoin(Lead, Lead.business_id == Business.id),
            user,
        )
    if order_id:
        stmt = stmt.where(Notification.order_id == order_id)
    return [
        {
            "id": n.id,
            "order_id": n.order_id,
            "channel": n.channel,
            "to": n.to_masked,
            "body": redact_tokens(n.body),
            "status": n.status,
            "at": n.created_at,
        }
        for n in db.scalars(stmt.order_by(Notification.id.desc()).limit(50)).unique()
    ]


@router.get("/audit")
def audit(user: Annotated[Me, Depends(admin_only)], db: Db):
    return [
        {"actor": a.actor, "event": a.event, "target": a.target, "at": a.at}
        for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100))
    ]
