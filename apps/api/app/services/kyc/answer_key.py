"""K01-K12 answer key, built by opening all 47 specimen images and checking
them against the registries and lead records (docs/kyc-answer-key.md).

applicant -> (expected verdict, phrase that must appear in a reason, finding)
"""

from functools import lru_cache

from app.core.config import get_settings

ANSWER_KEY: dict[str, tuple[str, str | None, str]] = {
    "K01": ("fail", "Cancelled", "GST registration cancelled; Udyam number blank"),
    "K02": ("pass", None, "Clean; certificate photographed at a tilt"),
    "K03": ("pass", None, "Clean"),
    "K04": ("fail", "too blurry", "GST certificate blurred"),
    "K05": ("incomplete", "Udyam certificate", "Udyam certificate not uploaded"),
    "K06": ("fail", "check digit", "GSTIN fails the checksum (tampered)"),
    "K07": ("fail", "does not match the GST registry", "Legal name altered"),
    "K08": ("pass", None, "Clean; OCR reads 0 for O in the GSTIN"),
    "K09": ("pass", None, "Clean"),
    "K10": ("review", "not the authorised contact", "Signatory isn't the contact on file"),
    "K11": ("fail", "days old", "Address proof 257 days old"),
    "K12": ("pass", None, "Clean"),
}
EXTRA_REASONS = {"K01": "Udyam registration number is missing"}
DOC_TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]


@lru_cache
def evaluate(applicant: str) -> tuple[str, list[str]]:
    """Full pipeline on one specimen applicant: OCR -> checks -> verdict."""
    from app.services.kyc.validators import analyse_document, cross_checks, required_docs, verdict

    docs = get_settings().data_dir / "kyc_documents"
    analyses = {}
    for t in DOC_TYPES:
        path = docs / f"{applicant}_{t}.png"
        if path.exists():
            analyses[t] = analyse_document(t, path.read_bytes())
    gst = analyses.get("gst_certificate")
    gstin = gst.fields.get("gstin") if gst and gst.readable else None
    udyam = analyses.get("udyam_certificate")
    udyam_no = udyam.fields.get("udyam_number") if udyam else None
    cross = cross_checks(analyses)
    checks = {t: a.checks + cross.get(t, []) for t, a in analyses.items()}
    return verdict(checks, required_docs(gstin, udyam_no))
