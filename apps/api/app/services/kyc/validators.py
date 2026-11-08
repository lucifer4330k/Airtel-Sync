"""Smart KYC validators.

analyse_document(): one document on its own -> fields + checks
cross_checks():     consistency across a case's documents + registries
verdict():          pass / review / fail / incomplete for the whole case

Every check is pass / fail / review with a reason an owner (or reviewer) can
act on. "review" never blocks the owner; it goes to the console queue.
"""

import csv
import re
from dataclasses import dataclass, field
from functools import lru_cache

from rapidfuzz import fuzz

from app.core.config import get_settings
from app.core.logging import mask_pii
from app.services.kyc.extract import Extracted, extract_fields, parse_date
from app.services.kyc.gstin_checksum import validate_gstin
from app.services.kyc.identity import UDYAM_FORMAT, Check, name_score
from app.services.kyc.ocr import BLUR_THRESHOLD, read_lines, sharpness
from app.services.registry import lookup_gstin, lookup_udyam

ADDRESS_PROOF_MAX_DAYS = 90
NAME_MATCH = 90
ADDRESS_MATCH = 85

DOC_LABEL = {
    "gst_certificate": "GST certificate",
    "udyam_certificate": "Udyam certificate",
    "signatory_id": "signatory ID",
    "address_proof": "address proof",
}
REQUIRED_FIELDS = {
    "gst_certificate": ("gstin", "legal_name"),
    "udyam_certificate": ("udyam_number", "enterprise_name"),
    "signatory_id": ("name", "valid_till"),
    "address_proof": ("billed_to", "address", "bill_date"),
}
# OCR confusables, corrected by position (GSTIN layout is fixed)
_TO_LETTER = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
_TO_DIGIT = {v: k for k, v in _TO_LETTER.items()}


@dataclass
class DocAnalysis:
    doc_type: str
    fields: dict[str, str] = field(default_factory=dict)
    title: str | None = None
    sharpness: float | None = None
    checks: list[Check] = field(default_factory=list)
    readable: bool = True


def correct_gstin(raw: str) -> str:
    g = re.sub(r"[^0-9A-Z]", "", raw.upper())
    if len(g) != 15:
        return g
    out = list(g)
    for i, c in enumerate(out):
        if i in (0, 1, 7, 8, 9, 10):
            out[i] = _TO_DIGIT.get(c, c)
        elif i in (2, 3, 4, 5, 6, 11):
            out[i] = _TO_LETTER.get(c, c)
        elif i == 13 and c == "2":
            out[i] = "Z"
    return "".join(out)


def _norm_addr(a: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", a.upper())


def _addr_match(a: str, b: str) -> bool:
    return fuzz.ratio(_norm_addr(a), _norm_addr(b)) >= ADDRESS_MATCH


@lru_cache
def _contacts_by_gstin() -> dict[str, tuple[str, str]]:
    """Registered contact (name, role) per GSTIN, from the lead records."""
    out = {}
    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["gstin"]:
                out[row["gstin"]] = (row["contact_name"], row["contact_role"])
    return out


def contact_for(gstin: str | None) -> str | None:
    return _contacts_by_gstin().get(gstin or "", (None,))[0]


# --- single document ------------------------------------------------------------


def analyse_document(doc_type: str, data: bytes) -> DocAnalysis:
    out = DocAnalysis(doc_type)
    out.sharpness = sharpness(data)
    if out.sharpness is not None and out.sharpness < BLUR_THRESHOLD:
        out.readable = False
        out.checks.append(
            Check(
                "image_quality",
                "fail",
                "The photo is too blurry to read. Please upload a sharper photo or scan.",
            )
        )
        return out
    if out.sharpness is None:
        # PDF or unreadable image: a person reads it
        out.readable = False
        out.checks.append(Check("document_reading", "review", "PDF received; a reviewer will read it"))
        return out

    ex: Extracted = extract_fields(doc_type, read_lines(data))
    out.title, out.fields = ex.title, dict(ex.fields)

    expected = {
        "gst_certificate": "gst",
        "udyam_certificate": "udyam",
        "signatory_id": "signatory",
        "address_proof": "bill",
    }
    if out.title and expected[doc_type] not in out.title.lower():
        out.checks.append(
            Check("document_type", "fail", f"This looks like a '{out.title}', not a {DOC_LABEL[doc_type]}.")
        )
        return out

    missing = [f for f in REQUIRED_FIELDS[doc_type] if not out.fields.get(f)]
    if doc_type == "udyam_certificate" and "udyam_number" in missing:
        out.checks.append(
            Check("udyam_number", "fail", "The Udyam registration number is missing on this certificate.")
        )
        missing.remove("udyam_number")
    if missing:
        out.checks.append(
            Check(
                "document_reading",
                "review",
                f"Could not read: {', '.join(missing)}. A reviewer will check it.",
            )
        )

    {
        "gst_certificate": _gst_checks,
        "udyam_certificate": _udyam_checks,
        "signatory_id": _id_checks,
        "address_proof": _address_checks,
    }[doc_type](out)
    return out


def _gst_checks(a: DocAnalysis) -> None:
    raw = a.fields.get("gstin")
    if not raw:
        return
    gstin = correct_gstin(raw)
    a.fields["gstin"] = gstin
    fmt = validate_gstin(gstin)
    if not fmt.ok:
        a.checks.append(
            Check(
                "gstin_valid",
                "fail",
                f"GSTIN {mask_pii(gstin)} on the certificate is not valid: {fmt.reason}.",
            )
        )
        return
    a.checks.append(Check("gstin_valid", "pass", "GSTIN format and checksum are valid"))
    rec = lookup_gstin(gstin)
    if rec is None:
        a.checks.append(Check("gstin_registry", "fail", "This GSTIN is not in the GST registry."))
        return
    if rec["status"] != "Active":
        a.checks.append(
            Check("gstin_registry", "fail", f"GST registration is {rec['status']}. It must be Active.")
        )
    else:
        a.checks.append(Check("gstin_registry", "pass", "GST registration is Active"))
    legal = a.fields.get("legal_name", "")
    if legal:
        score = fuzz.token_sort_ratio(legal.upper(), rec["legal_name"].upper())
        if score >= NAME_MATCH:
            a.checks.append(Check("gst_name", "pass", "Legal name matches the GST registry"))
        else:
            a.checks.append(
                Check(
                    "gst_name",
                    "fail",
                    f"Legal name on the certificate ('{legal}') does not match the GST registry ('{rec['legal_name']}').",
                )
            )
    addr = a.fields.get("address")
    if addr and not _addr_match(addr, rec["principal_place_of_business"]):
        a.checks.append(
            Check("gst_address", "review", "Address on the certificate differs from the GST registry.")
        )


def _udyam_checks(a: DocAnalysis) -> None:
    number = (a.fields.get("udyam_number") or "").upper()
    if not number:
        return
    if not UDYAM_FORMAT.match(number):
        a.checks.append(Check("udyam_valid", "fail", "Udyam number should look like UDYAM-MH-00-1234567."))
        return
    rec = lookup_udyam(number)
    if rec is None:
        a.checks.append(Check("udyam_registry", "fail", "This Udyam number is not in the Udyam registry."))
        return
    a.checks.append(Check("udyam_registry", "pass", "Udyam number is registered"))
    name = a.fields.get("enterprise_name", "")
    if name and fuzz.token_sort_ratio(name.upper(), rec["enterprise_name"].upper()) < NAME_MATCH:
        a.checks.append(
            Check(
                "udyam_name",
                "fail",
                f"Enterprise name differs from the Udyam registry ('{rec['enterprise_name']}').",
            )
        )


def _id_checks(a: DocAnalysis) -> None:
    today = get_settings().reference_date
    valid = parse_date(a.fields.get("valid_till"))
    if valid is None:
        return
    if valid < today:
        a.checks.append(
            Check("id_validity", "fail", f"The signatory ID expired on {valid:%d %b %Y}. Upload a valid ID.")
        )
    else:
        a.checks.append(Check("id_validity", "pass", f"ID valid till {valid:%d %b %Y}"))
    # Data minimisation: keep only the name and a masked ID number.
    if num := a.fields.get("id_number"):
        a.fields["id_number"] = ("X" * max(0, len(num) - 4)) + num[-4:]
    a.fields.pop("designation", None)


def _address_checks(a: DocAnalysis) -> None:
    today = get_settings().reference_date
    billed = parse_date(a.fields.get("bill_date"))
    if billed is None:
        return
    age = (today - billed).days
    if age > ADDRESS_PROOF_MAX_DAYS:
        a.checks.append(
            Check(
                "address_proof_date",
                "fail",
                f"The bill is dated {billed:%d %b %Y}, {age} days old. Upload one from the last {ADDRESS_PROOF_MAX_DAYS} days.",
            )
        )
    elif age < 0:
        a.checks.append(
            Check("address_proof_date", "review", f"The bill is dated in the future ({billed:%d %b %Y}).")
        )
    else:
        a.checks.append(
            Check(
                "address_proof_date",
                "pass",
                f"Bill dated {billed:%d %b %Y}, within {ADDRESS_PROOF_MAX_DAYS} days",
            )
        )


# --- across documents ------------------------------------------------------------


def _prop_name(legal_name: str) -> str | None:
    """'Neha Kaur (Prop. Vindhya Tours)' -> 'Neha Kaur'."""
    m = re.match(r"\s*(.+?)\s*\(prop", legal_name, re.IGNORECASE)
    return m.group(1) if m else None


def cross_checks(docs: dict[str, DocAnalysis], typed_gstin: str | None = None) -> dict[str, list[Check]]:
    out: dict[str, list[Check]] = {k: [] for k in docs}
    gst = docs.get("gst_certificate")
    gst_rec = None
    gstin = None
    if gst and gst.readable and gst.fields.get("gstin"):
        gstin = gst.fields["gstin"]
        gst_rec = lookup_gstin(gstin)
        if typed_gstin and correct_gstin(typed_gstin) != gstin:
            out["gst_certificate"].append(
                Check("gstin_typed", "fail", "The GSTIN on the certificate differs from the one you entered.")
            )
    gstin = gstin or typed_gstin

    # business names across documents
    names = [n for n in (gst.fields.get("legal_name"), gst.fields.get("trade_name")) if n] if gst else []
    ref = gst_rec or ({"legal_name": names[0], "trade_name": names[-1]} if names else None)

    def same_business(name: str | None) -> bool:
        return not name or not ref or name_score(name, ref) >= 85

    if (
        (u := docs.get("udyam_certificate"))
        and u.readable
        and not same_business(u.fields.get("enterprise_name"))
    ):
        out["udyam_certificate"].append(
            Check(
                "business_match",
                "review",
                "Udyam enterprise name differs from the GST name. A reviewer will confirm.",
            )
        )
    sig = docs.get("signatory_id")
    if sig and sig.readable and not same_business(sig.fields.get("business")):
        out["signatory_id"].append(
            Check("business_match", "review", "The ID is issued for a different business name.")
        )
    ap = docs.get("address_proof")
    if ap and ap.readable:
        if not same_business(ap.fields.get("billed_to")):
            out["address_proof"].append(
                Check("billed_to", "review", "The bill is in a different name than the business.")
            )
        gst_addr = (gst_rec or {}).get("principal_place_of_business") or (
            gst.fields.get("address") if gst else None
        )
        if gst_addr and ap.fields.get("address") and not _addr_match(ap.fields["address"], gst_addr):
            out["address_proof"].append(
                Check(
                    "address_match", "fail", "The supply address on the bill does not match the GST address."
                )
            )
        elif gst_addr and ap.fields.get("address"):
            out["address_proof"].append(
                Check("address_match", "pass", "Address matches the GST registration")
            )

    # signatory must be the proprietor, or the contact on file
    if sig and sig.readable and (person := sig.fields.get("name")):
        legal = (gst_rec or {}).get("legal_name") or (gst.fields.get("legal_name") if gst else "") or ""
        proprietor = _prop_name(legal)
        contact = contact_for(gstin)
        if proprietor:
            if fuzz.token_sort_ratio(person.upper(), proprietor.upper()) < NAME_MATCH:
                out["signatory_id"].append(
                    Check(
                        "signatory_match",
                        "fail",
                        f"The ID holder is not the proprietor named on the GST registration ({proprietor}).",
                    )
                )
            else:
                out["signatory_id"].append(
                    Check("signatory_match", "pass", "ID holder is the registered proprietor")
                )
        elif contact:
            if fuzz.token_sort_ratio(person.upper(), contact.upper()) < NAME_MATCH:
                out["signatory_id"].append(
                    Check(
                        "signatory_match",
                        "review",
                        f"The ID holder ({person}) is not the authorised contact on file ({contact}). "
                        "A reviewer will confirm their authority to sign.",
                    )
                )
            else:
                out["signatory_id"].append(
                    Check("signatory_match", "pass", "ID holder is the authorised contact on file")
                )
    return out


def required_docs(gstin: str | None, udyam_number: str | None) -> list[str]:
    """GST and/or Udyam certificate for whichever registration exists, plus ID and address proof."""
    docs = []
    has_udyam = bool(udyam_number)
    if gstin:
        docs.append("gst_certificate")
        rec = lookup_gstin(gstin)
        # The registry/lead says this business holds a Udyam registration too.
        if rec and not has_udyam:
            has_udyam = _has_udyam_on_file(gstin)
    if has_udyam:
        docs.append("udyam_certificate")
    return docs + ["signatory_id", "address_proof"]


@lru_cache
def _udyam_by_gstin() -> dict[str, str]:
    out = {}
    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["gstin"] and row["udyam_number"]:
                out[row["gstin"]] = row["udyam_number"]
    return out


def _has_udyam_on_file(gstin: str) -> bool:
    return gstin in _udyam_by_gstin()


def verdict(checks_by_doc: dict[str, list[Check]], required: list[str]) -> tuple[str, list[str]]:
    """Overall result and the reasons that drive it."""
    flat = [c for checks in checks_by_doc.values() for c in checks]
    fails = [c.reason for c in flat if c.result == "fail"]
    if fails:
        return "fail", fails
    missing = [d for d in required if d not in checks_by_doc]
    if missing:
        return "incomplete", [f"Upload your {DOC_LABEL[d]}." for d in missing]
    reviews = [c.reason for c in flat if c.result == "review"]
    if reviews:
        return "review", reviews
    return "pass", []
