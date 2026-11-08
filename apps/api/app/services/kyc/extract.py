"""Turn OCR lines into typed fields per document type.

The specimen layout is a two-column form: label on the left, value on the
right of the same row. Values that wrap continue on the next row with a
continuation label ("place of business") or none at all.
"""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.services.kyc.ocr import Line

TITLES = {
    "gst_certificate": "GST Registration Certificate",
    "udyam_certificate": "Udyam Registration Certificate",
    "signatory_id": "Authorised Signatory ID",
    "address_proof": "Bill",  # electricity / telephone / water bill
}

# canonical field -> label variants as printed
LABELS: dict[str, dict[str, tuple[str, ...]]] = {
    "gst_certificate": {
        "gstin": ("GSTIN",),
        "legal_name": ("Legal name",),
        "trade_name": ("Trade name",),
        "constitution": ("Constitution",),
        "address": ("Address of principal", "place of business"),
        "liability_date": ("Date of liability",),
        "registration_type": ("Type of registration",),
    },
    "udyam_certificate": {
        "udyam_number": ("Udyam reg. number", "Udyam registration number"),
        "enterprise_name": ("Enterprise name",),
        "major_activity": ("Major activity",),
        "city": ("City",),
        "state": ("State",),
        "registration_date": ("Date of registration",),
    },
    "signatory_id": {
        "name": ("Name",),
        "designation": ("Designation",),
        "business": ("For business",),
        "id_number": ("ID no.", "ID number"),
        "valid_till": ("Valid till", "Valid upto", "Expiry"),
    },
    "address_proof": {
        "consumer_number": ("Consumer no.", "Account no.", "Customer no."),
        "billed_to": ("Billed to",),
        "address": ("Supply address", "Service address", "Address"),
        "bill_date": ("Bill date", "Statement date"),
        "units": ("Units consumed",),
        "amount": ("Amount due (INR)", "Amount due"),
    },
}

NOISE = re.compile(r"specimen|synthetic|hackathon|fictional|format for|not a valid|testing only", re.I)
DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


@dataclass
class Extracted:
    doc_type: str
    title: str | None
    fields: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0

    def get(self, key: str) -> str | None:
        v = self.fields.get(key)
        return v or None


def _label_of(text: str, doc_type: str) -> str | None:
    t = text.strip().rstrip(":").lower()
    best, best_score = None, 0.0
    for key, variants in LABELS[doc_type].items():
        for v in variants:
            s = fuzz.ratio(t, v.lower())
            if s > best_score:
                best, best_score = key, s
    return best if best_score >= 85 else None


def _title(lines: list[Line]) -> str | None:
    for ln in lines[:4]:
        if ln.text.lower().startswith("specimen"):
            return ln.text.split(":", 1)[-1].strip()
    return None


def extract_fields(doc_type: str, lines: list[Line]) -> Extracted:
    title = _title(lines)
    lines = [ln for ln in lines if ln.text and not NOISE.search(ln.text)]
    if not lines:
        return Extracted(doc_type, title)
    split_x = 0.4 * max(ln.x1 for ln in lines)  # label column ends ~40% across

    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda ln: ln.yc):
        if rows and abs(rows[-1][0].yc - ln.yc) < 0.6 * (ln.y1 - ln.y0):
            rows[-1].append(ln)
        else:
            rows.append([ln])

    out = Extracted(doc_type, title)
    current: str | None = None
    scores: list[float] = []
    pending: str | None = None  # stacked layout: label row, value on the next row
    for row in rows:
        whole = " ".join(x.text for x in sorted(row, key=lambda x: x.x0))
        if pending:
            out.fields.setdefault(pending, whole.strip())
            scores += [x.score for x in row]
            pending = None
            continue
        stacked_key = _label_of(whole, doc_type)
        if stacked_key and len(row) == 1 and row[0].x0 > split_x - 40:
            pending = stacked_key
            continue
        left = " ".join(x.text for x in sorted(row, key=lambda x: x.x0) if x.x1 <= split_x + 40)
        right = " ".join(x.text for x in sorted(row, key=lambda x: x.x0) if x.x0 > split_x - 40)
        key = _label_of(left, doc_type) if left else None
        if key:
            if key == current and key == "address":  # continuation label of a wrapped value
                out.fields[key] = f"{out.fields.get(key, '')}{right}".strip()
            else:
                out.fields.setdefault(key, right.strip())
                current = key
            scores += [x.score for x in row]
        elif current == "address" and right and not left:
            out.fields["address"] = f"{out.fields['address']}{right}".strip()
    out.confidence = round(sum(scores) / len(scores), 3) if scores else 0.0
    for k in ("gstin", "udyam_number", "id_number"):
        if out.fields.get(k):
            out.fields[k] = out.fields[k].replace(" ", "").upper()
    return out


def parse_date(text: str | None):
    from datetime import date

    if not text or not (m := DATE.search(text)):
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
