"""Optional LLM help for the advisor, via LangChain (Gemini or OpenAI).

Two narrow jobs, both guarded:
  enrich(): read free text into slots the rule extractor missed. Output is a
            typed schema and every value is range-checked before use.
  polish(): rephrase a drafted reply in the owner's language. Rejected (draft
            kept) if any price or product name changes or a new product appears.
Identifiers are masked before any text leaves the server. With no API key,
available() is False and the advisor runs fully offline.
"""

import logging
import re
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import mask_pii
from app.services.advisor.extract import Extracted
from app.services.advisor.knowledge import NEEDS, city_tiers
from app.services.catalogue import get_catalogue

log = logging.getLogger(__name__)
_PRICE = re.compile(r"₹[\d,]+")


class SlotUpdate(BaseModel):
    """What the owner's message says about their business (null when not said)."""

    segment: Literal["micro", "prof", "multi", "mfg"] | None = Field(
        None,
        description="micro=single shop/retail/services, prof=clinic/office/agency, multi=3+ branches, mfg=factory",
    )
    business_type: str | None = Field(None, description="e.g. Kirana store, Dental clinic, Textile unit")
    employees: int | None = Field(None, ge=1, le=10000)
    sites: int | None = Field(None, ge=1, le=500)
    city: str | None = None
    has_gstin: bool | None = None
    needs: list[str] = Field(
        default_factory=list, description="short English needs like 'cctv', 'upi', 'wifi', 'email'"
    )
    wants_human: bool = False


@lru_cache
def _model():
    s = get_settings()
    try:
        if s.llm_provider == "gemini" and s.google_api_key:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=s.gemini_model, google_api_key=s.google_api_key, temperature=0, timeout=8, max_retries=1
            )
        if s.llm_provider == "openai" and s.openai_api_key:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=s.openai_model, api_key=s.openai_api_key, temperature=0, timeout=8, max_retries=1
            )
    except ImportError:
        log.warning("LLM provider configured but its LangChain package is not installed")
    return None


def available() -> bool:
    return _model() is not None


def enrich(ex: Extracted, text: str, slots: dict, awaiting: str | None) -> None:
    model = _model()
    if model is None:
        return
    try:
        upd: SlotUpdate = model.with_structured_output(SlotUpdate).invoke(
            [
                (
                    "system",
                    "Extract facts about a small Indian business from the owner's message. "
                    "The message may be English, Hindi or Hinglish. Only fill fields the message states. "
                    f"The assistant just asked about: {awaiting or 'nothing'}.",
                ),
                ("human", mask_pii(text)),
            ]
        )
    except Exception as exc:  # noqa: BLE001 - any provider error falls back to rules
        log.warning("LLM extract failed: %s", exc.__class__.__name__)
        return
    ex.segment = ex.segment or upd.segment
    ex.business_type = ex.business_type or upd.business_type
    ex.employees = ex.employees or upd.employees
    ex.sites = ex.sites or upd.sites
    if upd.city and not ex.city and (tier := city_tiers().get(upd.city.lower())):
        ex.city, ex.city_tier = upd.city.title(), tier
    if ex.has_gstin is None and upd.has_gstin is not None and not ex.gstin:
        ex.has_gstin = upd.has_gstin
    mapped = {NEEDS[n.lower()] for n in upd.needs if n.lower() in NEEDS}
    ex.needs = sorted(set(ex.needs) | mapped)
    ex.wants_human = ex.wants_human or upd.wants_human


def polish(draft: str, lang: str) -> str:
    model = _model()
    if model is None:
        return draft
    target = {"hi": "Hindi in Devanagari script", "hinglish": "Hinglish (Hindi in Latin script)"}.get(
        lang, "simple English"
    )
    try:
        out = model.invoke(
            [
                (
                    "system",
                    f"Rewrite the assistant message warmly and briefly in {target}. Keep every ₹ amount, number and "
                    "product name exactly as written. Do not add products, prices or promises. Keep bullet lines. "
                    "Return only the message.",
                ),
                ("human", draft),
            ]
        ).content
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM polish failed: %s", exc.__class__.__name__)
        return draft
    if not isinstance(out, str) or not out.strip():
        return draft
    names = {p.name for p in get_catalogue().values()}
    kept_prices = set(_PRICE.findall(draft)) <= set(_PRICE.findall(out))
    kept_names = all(n in out for n in names if n in draft)
    added = [n for n in names if n in out and n not in draft]
    return out.strip() if kept_prices and kept_names and not added else draft
