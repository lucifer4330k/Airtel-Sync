"""Registry-backed identity checks: GSTIN and Udyam number.

Each check returns pass / fail / review with a reason an owner can act on.
"""

import re
from dataclasses import asdict, dataclass

from rapidfuzz import fuzz

from app.services.kyc.gstin_checksum import validate_gstin
from app.services.registry import lookup_gstin, lookup_udyam

UDYAM_FORMAT = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
NAME_MATCH_THRESHOLD = 85
# Proprietorship legal names look like "Sneha Rao (Prop. Saffron Bakers)";
# the Udyam certificate carries only the trade name.
_PROP = re.compile(r"\(prop\.?\s*(.+?)\)", re.IGNORECASE)


@dataclass(frozen=True)
class Check:
    name: str
    result: str  # pass / fail / review
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


def gstin_checks(gstin: str) -> list[Check]:
    fmt = validate_gstin(gstin)
    if not fmt.ok:
        return [Check("gstin_format", "fail", fmt.reason)]
    checks = [Check("gstin_format", "pass", fmt.reason)]
    rec = lookup_gstin(gstin)
    if rec is None:
        checks.append(Check("gstin_registry", "fail", "This GSTIN is not in the GST registry"))
        return checks
    status = rec["status"]
    if status == "Active":
        checks.append(Check("gstin_registry", "pass", f"Registered to {rec['legal_name']}, status Active"))
    else:
        checks.append(
            Check(
                "gstin_registry",
                "fail",
                f"GST registration is {status}. Services that need GST cannot be activated "
                "until it is Active again.",
            )
        )
    return checks


def _name_candidates(gst_record: dict) -> list[str]:
    names = [gst_record["legal_name"], gst_record["trade_name"]]
    m = _PROP.search(gst_record["legal_name"])
    if m:
        names.append(m.group(1))
    return names


def name_score(name: str, gst_record: dict) -> float:
    return max(fuzz.token_sort_ratio(name.upper(), c.upper()) for c in _name_candidates(gst_record))


def udyam_checks(udyam_number: str, gstin: str | None) -> list[Check]:
    number = udyam_number.strip().upper()
    if not UDYAM_FORMAT.match(number):
        return [Check("udyam_format", "fail", "Udyam number should look like UDYAM-MH-00-1234567")]
    checks = [Check("udyam_format", "pass", "Udyam number format is valid")]
    rec = lookup_udyam(number)
    if rec is None:
        checks.append(Check("udyam_registry", "fail", "This Udyam number is not in the Udyam registry"))
        return checks
    checks.append(Check("udyam_registry", "pass", f"Registered to {rec['enterprise_name']}"))

    gst = lookup_gstin(gstin) if gstin else None
    if gst is not None:
        score = name_score(rec["enterprise_name"], gst)
        if score >= NAME_MATCH_THRESHOLD:
            checks.append(Check("udyam_gst_name_match", "pass", "Udyam and GST names match"))
        else:
            checks.append(
                Check(
                    "udyam_gst_name_match",
                    "review",
                    f"Udyam name '{rec['enterprise_name']}' differs from GST name "
                    f"'{gst['legal_name']}'. A reviewer will confirm they are the same business.",
                )
            )
    return checks


def overall(checks: list[Check]) -> str:
    results = {c.result for c in checks}
    if "fail" in results:
        return "fail"
    if "review" in results:
        return "review"
    return "pass"
