"""Lead propensity: P(activated) with its top three reasons.

The served model is the logistic regression trained by ml/train_propensity.py
(exported as JSON). For a linear model, coefficient x (value - training mean)
is exactly the feature's SHAP value, so the reasons are faithful, not a
post-hoc approximation.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from app.services.catalogue import get_catalogue
from app.services.eligibility import BusinessProfile, eligible
from app.services.registry import gstin_is_active

MODEL_PATH = Path(__file__).with_name("propensity_model.json")
SEGMENT_NAMES = {
    "micro": "Micro retail & services",
    "prof": "Professional offices",
    "multi": "Small multi-site businesses",
    "mfg": "Small manufacturers",
}
FRIENDLY = {
    "segment": "Segment: {v}",
    "business_type": "Business type: {v}",
    "lead_source": "Came via {v}",
    "city_tier": "Tier-{v} city",
    "preferred_language": "Prefers {v}",
    "annual_turnover_band": "Turnover {v}",
    "current_internet": "Currently on {v}",
    "log_employees": "{n} employees",
    "log_sites": "{n} site(s)",
    "log_spend": "Spends ₹{n}/month on telecom",
    "n_products": "Asked about {n} product(s)",
    "has_gstin": "Has GST registration",
    "has_udyam": "Has Udyam registration",
    "any_ineligible": "Asked for a product they can't get yet",
}


@lru_cache
def _model() -> dict | None:
    return json.loads(MODEL_PATH.read_text()) if MODEL_PATH.exists() else None


def lead_features(
    *,
    segment: str,
    business_type: str | None,
    source: str,
    city_tier: int,
    language: str | None,
    turnover_band: str | None,
    current_internet: str | None,
    employees: int,
    sites: int,
    telecom_spend: int | None,
    products: list[str],
    gstin: str | None,
    has_udyam: bool,
) -> dict:
    biz = BusinessProfile(segment, city_tier, employees, sites, gstin_is_active(gstin))
    catalogue = get_catalogue()
    return {
        "segment": SEGMENT_NAMES.get(segment, segment),
        "business_type": business_type or "",
        "lead_source": source,
        "city_tier": str(city_tier),
        "preferred_language": {"en": "English", "hi": "Hindi", "hinglish": "Hindi"}.get(
            language or "", language or ""
        ),
        "annual_turnover_band": turnover_band or "",
        "current_internet": current_internet or "",
        "log_employees": math.log1p(employees),
        "log_sites": math.log1p(sites),
        "log_spend": math.log1p(telecom_spend or 0),
        "n_products": len(products),
        "has_gstin": int(bool(gstin)),
        "has_udyam": int(has_udyam),
        "any_ineligible": int(any(p in catalogue and not eligible(catalogue[p], biz).ok for p in products)),
    }


def score(features: dict) -> tuple[float, list[dict]] | None:
    m = _model()
    if m is None:
        return None
    contrib: dict[str, float] = {}
    for name, spec in m["numeric"].items():
        contrib[name] = spec["coef"] * (features[name] - spec["mean"]) / spec["std"]
    for name, levels in m["categorical"].items():
        value = str(features.get(name, ""))
        expected = sum(coef * m["baseline"].get(f"{name}_{lvl}", 0.0) for lvl, coef in levels.items())
        contrib[name] = levels.get(value, 0.0) - expected
    logit = (
        m["intercept"]
        + sum(spec["coef"] * (features[n] - spec["mean"]) / spec["std"] for n, spec in m["numeric"].items())
        + sum(levels.get(str(features.get(n, "")), 0.0) for n, levels in m["categorical"].items())
    )
    # The model was trained with balanced class weights: rescale to the real base rate.
    base = m["base_rate"]
    odds = math.exp(logit) * base / (1 - base)
    p = odds / (1 + odds)

    def label(name: str) -> str:
        v = features.get(name)
        if name in ("log_employees", "log_sites", "log_spend"):
            return FRIENDLY[name].format(n=round(math.expm1(v)))
        return FRIENDLY[name].format(v=v, n=v)

    top = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))
    reasons = [
        {"feature": n, "label": label(n), "effect": "up" if c > 0 else "down", "weight": round(c, 3)}
        for n, c in top
        if abs(c) > 0.02
        and not (n in ("has_gstin", "has_udyam", "any_ineligible") and features[n] == 0 and c > 0)
    ][:3]
    return round(p, 4), reasons


def score_lead(db, lead) -> None:
    """Fill lead.propensity_score / score_reasons from its business record."""
    from app.models import Business

    biz = db.get(Business, lead.business_id)
    if biz is None:
        return
    out = score(
        lead_features(
            segment=biz.segment,
            business_type=biz.type,
            source=lead.source,
            city_tier=biz.tier,
            language=biz.language,
            turnover_band=biz.turnover_band,
            current_internet=biz.current_internet,
            employees=biz.employees,
            sites=biz.sites,
            telecom_spend=biz.telecom_spend,
            products=lead.products_of_interest or [],
            gstin=biz.gstin,
            has_udyam=bool(biz.udyam_number),
        )
    )
    if out:
        lead.propensity_score, lead.score_reasons = out
