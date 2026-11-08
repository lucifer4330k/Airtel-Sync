"""The advisor's controller.

The server owns the conversation and every product decision:
  extract_profile -> (ask the next missing slot) -> recommend_bundle (rules
  engine) -> explain. An LLM, when configured, only helps read free text and
  phrase replies; it never chooses products, and anything it returns is
  re-validated here.

At most six questions; anything still unknown gets a conservative default
(tier-2 city, one site) so nothing ineligible can slip in.
"""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging import mask_pii
from app.core.security import kyc_token
from app.models import AdvisorMessage, AdvisorSession, Business, Lead
from app.services import leads as lead_svc
from app.services import quotes as quote_svc
from app.services.advisor import llm
from app.services.advisor.explain import ineligible_note, reason
from app.services.advisor.extract import Extracted, detect_language, extract
from app.services.advisor.replies import CHIP_MEANING, NOTHING_ELSE, chips, t
from app.services.catalogue import get_catalogue
from app.services.kyc.gstin_checksum import validate_gstin
from app.services.registry import lookup_gstin

log = logging.getLogger(__name__)
MAX_QUESTIONS = 6
SLOT_ORDER = ["segment", "employees", "sites", "city", "gst", "needs"]
DEFAULT_STAFF = {"micro": 2, "prof": 5, "multi": 15, "mfg": 12}
SURVEY_PRODUCTS = {"P05", "P06"}


def _inr(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return f"₹{s}"
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts) + "," + tail


def _merge(slots: dict, ex: Extracted) -> None:
    for key in (
        "business_type",
        "segment",
        "employees",
        "sites",
        "city",
        "city_tier",
        "current_internet",
        "phone",
    ):
        value = getattr(ex, key)
        if value is not None:
            slots[key] = value
    if ex.gstin:
        slots["gstin"], slots["has_gstin"] = ex.gstin, True
        slots.pop("gst_status", None)
    elif ex.has_gstin is not None and "gstin" not in slots:
        slots["has_gstin"] = ex.has_gstin
    if ex.needs:
        slots["needs"] = sorted(set(slots.get("needs", [])) | set(ex.needs))
    # Shape the segment from the size, as in the lead data.
    seg, sites = slots.get("segment"), slots.get("sites")
    if seg == "micro" and sites and sites >= 2 or seg in ("prof", "mfg") and sites and sites >= 3:
        slots["segment"] = "multi"
        slots.setdefault("business_type", "Retail chain")


def _missing(slots: dict) -> str | None:
    if not slots.get("segment"):
        return "segment"
    if not slots.get("employees"):
        return "employees"
    if not slots.get("sites"):
        if slots["segment"] == "micro":
            slots["sites"] = 1  # a single shop; chains say "branches"
        else:
            return "sites"
    if not slots.get("city_tier"):
        return "city"
    if "has_gstin" not in slots:
        return "gst"
    if slots.get("has_gstin") and not slots.get("gstin") and not slots.get("gst_skip"):
        return "gst_number"
    if not slots.get("needs_done"):
        return "needs"
    return None


def _apply_defaults(slots: dict) -> None:
    """Out of questions: fill the rest conservatively (never widens eligibility)."""
    slots.setdefault("segment", "micro")
    slots.setdefault("employees", DEFAULT_STAFF[slots["segment"]])
    slots.setdefault("sites", 1)
    slots.setdefault("city_tier", 2)
    slots.setdefault("has_gstin", False)
    slots["needs_done"] = True
    if slots.get("has_gstin") and not slots.get("gstin"):
        slots["gst_skip"] = True


def _check_gst(slots: dict, lang: str) -> str | None:
    """Validates a newly given GSTIN. Returns a reply to send, if any."""
    gstin = slots.get("gstin")
    if not gstin or slots.get("gst_status"):
        return None
    fmt = validate_gstin(gstin)
    if not fmt.ok:
        slots.pop("gstin")
        slots["has_gstin"] = True
        return t("gst_invalid", lang, reason=fmt.reason)
    rec = lookup_gstin(gstin)
    if rec is None:
        slots.pop("gstin")
        return t("gst_invalid", lang, reason="not found in the GST registry")
    slots["gst_status"] = rec["status"]
    slots["gst_name"] = rec["legal_name"]
    if rec["status"] != "Active":
        return t("gst_inactive", lang, status=rec["status"])
    return t("gst_ok", lang, name=rec["legal_name"])


def _session_business(db: Session, session: AdvisorSession) -> tuple[Business | None, Lead | None]:
    if not session.lead_id:
        return None, None
    lead = db.get(Lead, session.lead_id)
    return db.get(Business, lead.business_id), lead


def _upsert_lead(db: Session, session: AdvisorSession, slots: dict) -> tuple[Business, Lead]:
    biz, _ = _session_business(db, session)
    verified_gstin = slots.get("gstin") if slots.get("gst_status") else None
    biz, lead = lead_svc.upsert(
        db,
        business=biz,
        segment=slots.get("segment", "micro"),
        city_tier=slots.get("city_tier", 2),
        employees=slots.get("employees") or DEFAULT_STAFF.get(slots.get("segment", "micro"), 1),
        sites=slots.get("sites") or 1,
        gstin=verified_gstin,
        phone=slots.get("phone"),
        business_type=slots.get("business_type"),
        city=slots.get("city"),
        language=session.language,
        current_internet=slots.get("current_internet"),
        products_of_interest=slots.get("needs"),
        channel=session.channel,
    )
    session.lead_id = lead.id
    return biz, lead


def _flag_human(lead: Lead, why: str) -> None:
    lead.needs_human = True
    lead.needs_human_reason = why if not lead.needs_human_reason else f"{lead.needs_human_reason}; {why}"


def _build_plan(db: Session, session: AdvisorSession, slots: dict, lang: str) -> tuple[str, dict]:
    catalogue = get_catalogue()
    biz, lead = _upsert_lead(db, session, slots)
    quotes = quote_svc.create_quotes(db, lead, biz)
    if not quotes:
        _flag_human(lead, "No standard plan fits")
        return t("human", lang), {}
    profile = quote_svc.profile_of(biz)

    # Add what they asked for to the richer plans, if the rules allow it.
    notes: list[str] = []
    targets = [q for q in quotes if q.tier in ("better", "best")] or quotes
    for pid in slots.get("needs", []):
        note = ineligible_note(pid, profile, lang)
        if note:
            notes.append(note)
            continue
        for q in targets:
            try:
                quote_svc.toggle(db, q, biz, pid, True)
            except HTTPException:
                pass

    recommended = next((q for q in quotes if q.tier == "better"), quotes[0])
    survey = {i.product_id for i in quote_svc._items(db, recommended)} & SURVEY_PRODUCTS
    if survey:  # leased lines always need a site survey before install
        _flag_human(lead, f"{catalogue[min(survey)].name} needs a site survey")
        notes.append(t("survey", lang))
    lead.suggested_bundle = {"recommended": recommended.id, "tiers": [q.tier for q in quotes]}
    items = quote_svc._items(db, recommended)

    bullets = [
        f"• {catalogue[i.product_id].name}: {reason(i.product_id, slots, lang) or ''}".rstrip(": ")
        for i in items
    ]
    sites = slots.get("sites") or 1
    sites_text = (
        ""
        if sites == 1
        else (
            f" और {sites} जगहें"
            if lang == "hi"
            else f" aur {sites} jagah"
            if lang == "hinglish"
            else f" across {sites} sites"
        )
    )
    intro = t(
        "plan_intro",
        lang,
        type=(slots.get("business_type") or "business").lower()
        if lang == "en"
        else (slots.get("business_type") or "business"),
        staff=slots.get("employees"),
        sites_text=sites_text,
    )
    outro = t("plan_outro", lang, price=_inr(recommended.monthly_total))
    text = "\n".join([intro, *bullets, *notes, outro])

    card = {
        "business_id": biz.id,
        "owner_token": kyc_token(biz.id),
        "recommended_quote_id": recommended.id,
        "quotes": [
            {"id": q.id, "tier": q.tier, "monthly_total": q.monthly_total, "setup_total": q.setup_total}
            for q in quotes
        ],
        "reasons": [
            {"product": catalogue[i.product_id].name, "reason": reason(i.product_id, slots, lang)}
            for i in items
        ],
        "notes": notes,
    }
    lead.stage = "Needs assessed"
    lead.stopped_at = "quote"
    return text, card


def start(db: Session, channel: str, language: str | None) -> tuple[AdvisorSession, dict]:
    lang = language if language in ("en", "hi", "hinglish") else "en"
    session = AdvisorSession(
        channel=channel, language=lang, slots={"questions": 1, "awaiting": "segment"}, status="open"
    )
    db.add(session)
    db.flush()
    greeting = t("greet", lang)
    db.add(AdvisorMessage(session_id=session.id, role="advisor", text=greeting))
    return session, {"reply": greeting, "chips": chips("segment", lang), "done": False}


def handle(db: Session, session: AdvisorSession, text: str) -> dict:
    slots = dict(session.slots or {})
    raw = text.strip()[:1000]
    db.add(AdvisorMessage(session_id=session.id, role="owner", text=mask_pii(raw)))

    # Language: follow the owner from their first real message.
    if not slots.get("lang_locked") and raw not in CHIP_MEANING:
        detected = detect_language(raw)
        if detected in ("hi", "hinglish") or slots.get("questions", 0) <= 1:
            session.language = detected if detected != "ta" else session.language
        slots["lang_locked"] = True
    lang = session.language if session.language in ("en", "hi", "hinglish") else "en"

    awaiting = slots.get("awaiting")
    meaning = CHIP_MEANING.get(raw, raw)
    ex = extract(meaning, awaiting="gst" if awaiting in ("gst", "gst_number") else awaiting)
    if llm.available():
        llm.enrich(ex, raw, slots, awaiting)  # fills only what rules missed; validated inside

    if awaiting == "gst_number" and meaning.lower() in ("skip", "no", "nahi", "नहीं"):
        slots["gst_skip"] = True
    # Needs stated at any point count as the answer; "nothing else" only when asked.
    if ex.needs or awaiting == "needs" and any(w in meaning.lower() for w in NOTHING_ELSE):
        slots["needs_done"] = True
    if awaiting == "city" and ex.city_tier is None and meaning and not ex.segment:
        slots["city"] = meaning.title()[:40]  # unknown city name: keep it, ask tier
    _merge(slots, ex)

    prefix: list[str] = []
    if ex.wants_human:
        _, lead = _upsert_lead(db, session, slots)
        _flag_human(lead, "Owner asked for a call")
        session.slots = slots
        reply = (
            t("human_ok", lang, phone=mask_pii(slots["phone"])) if slots.get("phone") else t("human", lang)
        )
        return _say(db, session, reply, [], done=bool(slots.get("done")), needs_human=True)

    if gst_reply := _check_gst(slots, lang):
        prefix.append(gst_reply)
        if not slots.get("gstin"):  # invalid: ask again
            slots["awaiting"] = "gst_number"
            session.slots = slots
            return _say(db, session, gst_reply, chips("gst", lang))

    if slots.get("done"):
        # After the plan: new needs or size changes update it.
        if ex.needs or ex.employees or ex.sites or ex.city_tier:
            text_out, card = _build_plan(db, session, slots, lang)
            session.slots = slots
            return _say(db, session, t("done_followup", lang) + "\n" + text_out, [], done=True, card=card)
        session.slots = slots
        return _say(
            db, session, t("unclear", lang) + " " + t("ask_needs", lang), chips("needs", lang), done=True
        )

    nxt = _missing(slots)
    if nxt and slots.get("questions", 0) >= MAX_QUESTIONS:
        _apply_defaults(slots)
        nxt = _missing(slots)

    if nxt:
        same_again = nxt == awaiting and not prefix
        slots["awaiting"] = nxt
        slots["questions"] = slots.get("questions", 0) + 1
        session.slots = slots
        key = {"gst_number": "ask_gst_number", "segment": "ask_segment"}.get(nxt, f"ask_{nxt}")
        chip_key = {"gst_number": "gst"}.get(nxt, nxt)
        body = t(key, lang)
        if same_again:
            body = t("unclear", lang) + " " + body
        return _say(db, session, "\n".join([*prefix, body]), chips(chip_key, lang))

    slots["awaiting"] = None
    slots["done"] = True
    text_out, card = _build_plan(db, session, slots, lang)
    session.slots = slots
    session.status = "done"
    return _say(db, session, "\n".join([*prefix, text_out]), [], done=True, card=card)


def _say(db, session, reply, chip_list, done=False, card=None, needs_human=False) -> dict:
    lang = session.language
    if llm.available():
        reply = llm.polish(reply, lang)  # keeps numbers and product names; falls back on error
    db.add(AdvisorMessage(session_id=session.id, role="advisor", text=mask_pii(reply)))
    return {
        "reply": reply,
        "chips": chip_list,
        "done": done,
        "bundle": card,
        "needs_human": needs_human,
        "language": lang,
        "slots": {
            k: v
            for k, v in (session.slots or {}).items()
            if k in ("segment", "employees", "sites", "city", "city_tier", "needs", "business_type")
        },
    }
