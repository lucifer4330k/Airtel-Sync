"""Rule-based slot extraction (the offline fallback and the LLM's safety net)."""

import re
from dataclasses import dataclass, field

from app.services.advisor import knowledge as K

GSTIN_IN_TEXT = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)
PHONE_IN_TEXT = re.compile(r"(?<!\d)(?:\+91[\s-]?)?([6-9]\d{9})(?!\d)")
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUM = r"(\d{1,4})"
_EMP_WORDS = (
    r"staff|employees?|people|persons?|workers?|members?|log|लोग|कर्मचारी|karmchari|doctors?|"
    r"team|assistants?|helpers?|ladke|आदमी|admi|teachers?|lawyers?|nurses?|engineers?|trainers?|"
    r"pharmacists?|chefs?|cooks?|stylists?|labou?rers?|karigar"
)
_SITE_WORDS = (
    r"branch(?:es)?|sites?|locations?|outlets?|stores|shops|clinics|offices|centres|centers|"
    r"branches|ब्रांच|शाखा|शाखाएं|dukane|dukaanein|jagah|जगह|units|factories|godowns?|hotels|gyms|"
    r"restaurants|schools|pharmacies|plants|warehouses"
)


@dataclass
class Extracted:
    business_type: str | None = None
    segment: str | None = None
    employees: int | None = None
    sites: int | None = None
    city: str | None = None
    city_tier: int | None = None
    gstin: str | None = None
    has_gstin: bool | None = None
    current_internet: str | None = None
    needs: list[str] = field(default_factory=list)
    wants_human: bool = False
    phone: str | None = None


def detect_language(text: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if re.search(r"[஀-௿]", text):
        return "ta"
    hinglish = (
        "hai",
        "hain",
        "mera",
        "meri",
        "humara",
        "hamara",
        "chahiye",
        "kya",
        "nahi",
        "dukaan",
        "log",
        "kitna",
    )
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & set(hinglish)) >= 2:
        return "hinglish"
    return "en"


def _normalise(text: str) -> str:
    t = text.translate(_DEVANAGARI_DIGITS).lower()
    for word, n in sorted(K.NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"(?<![\wऀ-ॿ]){re.escape(word)}(?![\wऀ-ॿ])", str(n), t)
    return t


def _has_word(text: str, word: str) -> bool:
    # whole word, optional English plural
    return re.search(rf"(?<![\wऀ-ॿ]){re.escape(word)}(?:s|es)?(?![\wऀ-ॿ])", text) is not None


def extract(text: str, awaiting: str | None = None) -> Extracted:
    """Pull every slot we can from one message. `awaiting` is the slot the
    advisor just asked about, so a bare "12" or "haan" can be attributed."""
    out = Extracted()
    raw = text.strip()
    t = _normalise(raw)

    if m := GSTIN_IN_TEXT.search(raw):
        out.gstin, out.has_gstin = m.group(0).upper(), True
    elif re.search(
        r"\b(no|nahi|nahin|without|not)\b.{0,12}\bgst|gst\b.{0,15}\b(nahi|nahin|no|not)\b|जीएसटी नहीं|gst नहीं",
        t,
    ):
        out.has_gstin = False
    elif awaiting == "gst":
        if any(_has_word(t, w) for w in K.NO_WORDS):
            out.has_gstin = False
        elif any(_has_word(t, w) for w in K.YES_WORDS):
            out.has_gstin = True

    if m := PHONE_IN_TEXT.search(raw.translate(_DEVANAGARI_DIGITS)):
        out.phone = m.group(1)

    for kw, (label, seg) in sorted(K.BUSINESS_TYPES.items(), key=lambda kv: -len(kv[0])):
        if _has_word(t, kw):
            out.business_type, out.segment = label, seg
            break

    if m := re.search(rf"{_NUM}\s*(?:-|\s)?\s*(?:{_EMP_WORDS})", t):
        out.employees = int(m.group(1))
    elif m := re.search(rf"(?:team|staff)\s+(?:of\s+)?{_NUM}", t):
        out.employees = int(m.group(1))
    if m := re.search(rf"{_NUM}\s*(?:-|\s)?\s*(?:{_SITE_WORDS})", t):
        out.sites = int(m.group(1))
    elif re.search(
        r"\b(single|one|ek hi|सिर्फ एक|only one)\b.{0,10}\b(shop|store|clinic|office|location|dukaan|branch)",
        t,
    ):
        out.sites = 1

    bare = re.fullmatch(r"\s*(\d{1,4})\s*\+?\s*", t)
    if bare and awaiting in ("employees", "sites"):
        setattr(out, awaiting, int(bare.group(1)))

    for dev, latin in K.DEVANAGARI_CITIES.items():
        if dev in raw:
            t += f" {latin}"
    for city, tier in sorted(K.city_tiers().items(), key=lambda kv: -len(kv[0])):
        if _has_word(t, city):
            out.city, out.city_tier = city.title(), tier
            break
    if out.city_tier is None and awaiting == "city":
        if re.search(r"metro|big city|bada shahar|बड़ा शहर|tier.?1", t):
            out.city_tier = 1
        elif re.search(r"small(er)? (city|town)|chhota|छोटा|tier.?2|town|kasba", t):
            out.city_tier = 2

    for kw, label in K.CURRENT_INTERNET.items():
        if _has_word(t, kw):
            out.current_internet = label
            break

    needs = {pid for kw, pid in K.NEEDS.items() if _has_word(t, kw)}
    if re.search(r"(have|using|use|current|existing|already).{0,20}leased line", t):
        out.current_internet = "Leased line"
        needs -= {"P05", "P06"}  # they already have one, not asking for one
    out.needs = sorted(needs)
    out.wants_human = any(_has_word(t, w) for w in K.HUMAN_WORDS)
    return out
