"""Judge challenge panel: pick or build a scenario, break it, and see the rule
the system applied. Stateless (no database, no personal data) and kept
separate from the customer journey."""

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.ratelimit import limit
from app.routers.quotes import WhatIfIn
from app.services.catalogue import SEGMENT_CODES, get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import build_tiers, price_bundle

router = APIRouter(prefix="/judge", tags=["judge"], dependencies=[Depends(limit(60, 60))])
SCORECARD = Path(__file__).resolve().parents[1] / "services" / "scorecard.json"

SCENARIOS = [
    {
        "id": "clinic",
        "label": "5-person clinic, Pune, GST active",
        "profile": {"segment": "prof", "city_tier": 1, "employees": 5, "sites": 1, "gstin_active": True},
        "try": "Set a ₹2,000 budget, add Backup 4G/5G Failover and mark it essential.",
    },
    {
        "id": "kirana",
        "label": "Kirana in a tier-2 city, no GST",
        "profile": {"segment": "micro", "city_tier": 2, "employees": 3, "sites": 1, "gstin_active": False},
        "try": "Add WhatsApp Business API or Biz Fibre 1G and see what the rules allow instead.",
    },
    {
        "id": "chain",
        "label": "Restaurant chain, 4 outlets, 40 staff",
        "profile": {"segment": "multi", "city_tier": 1, "employees": 40, "sites": 4, "gstin_active": True},
        "try": "Grow to 8 sites, then switch the connection to 5G AirFiber.",
    },
    {
        "id": "factory",
        "label": "Textile unit, Surat, 30 workers",
        "profile": {"segment": "mfg", "city_tier": 2, "employees": 30, "sites": 1, "gstin_active": True},
        "try": "Ask for Biz Fibre 1G (tier-1 only), then lose the GST registration.",
    },
    {
        "id": "small-office",
        "label": "4-person law office wanting 1 Gbps",
        "profile": {"segment": "prof", "city_tier": 1, "employees": 4, "sites": 1, "gstin_active": True},
        "try": "Add Biz Fibre 1G (needs 5 employees), then change staff to 6.",
    },
]


class ProfileIn(BaseModel):
    segment: str
    city_tier: Literal[1, 2]
    employees: int = Field(ge=1, le=10_000)
    sites: int = Field(ge=1, le=500)
    gstin_active: bool = False

    def biz(self) -> BusinessProfile:
        seg = SEGMENT_CODES.get(self.segment, self.segment)
        if seg not in {"micro", "prof", "multi", "mfg"}:
            raise HTTPException(422, f"Unknown segment '{self.segment}'")
        return BusinessProfile(seg, self.city_tier, self.employees, self.sites, self.gstin_active)


class ChallengeIn(BaseModel):
    profile: ProfileIn
    items: dict[str, int] = Field(max_length=25)
    change: WhatIfIn
    # Judges may also test gaining staff (not an owner what-if)
    employees: int | None = Field(None, ge=1, le=10_000)


def _rules_table(biz: BusinessProfile) -> list[dict]:
    rows = []
    for p in get_catalogue().values():
        e = eligible(p, biz)
        rows.append(
            {
                "product_id": p.product_id,
                "name": p.name,
                "category": p.category,
                "eligible": e.ok,
                "rules": list(e.rules),
                "reasons": list(e.reasons),
                "needs_one_of": list(p.requires_one_of),
            }
        )
    return rows


@router.get("/scenarios")
def scenarios():
    return SCENARIOS


@router.post("/plan")
def plan(profile: ProfileIn):
    biz = profile.biz()
    return {"tiers": build_tiers(biz), "rules": _rules_table(biz)}


@router.post("/challenge")
def challenge(body: ChallengeIn):
    from dataclasses import replace

    from app.services.repair import analyse

    catalogue = get_catalogue()
    if any(p not in catalogue for p in body.items):
        raise HTTPException(422, "Unknown product in items")
    biz = body.profile.biz()
    req = body.change.request()
    if body.employees:
        req = replace(req, employees=body.employees)
    try:
        result = analyse(body.items, biz, req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    before = price_bundle(body.items, biz) if body.items else None
    changed = replace(
        biz,
        sites=req.sites or biz.sites,
        city_tier=req.city_tier or biz.city_tier,
        employees=req.employees or biz.employees,
        gstin_active=biz.gstin_active if req.gstin_active is None else req.gstin_active,
    )
    # Independent re-check of every option, shown to the judge.
    audit = []
    for o in result.options:
        if o.kind == "handoff":
            continue
        bad = [p for p in o.items if not eligible(catalogue[p], changed).ok]
        audit.append(
            {"option": o.id, "ineligible": bad, "dependencies_ok": validate_bundle(o.items.keys()).ok}
        )
    return {
        "before_total": before.monthly_total if before else 0,
        **result.as_dict(),
        "audit": audit,
        "rules_after": _rules_table(changed),
    }


@router.get("/scorecard")
def scorecard():
    if not SCORECARD.exists():
        return {"available": False}
    return {"available": True, **json.loads(SCORECARD.read_text(encoding="utf-8"))}
