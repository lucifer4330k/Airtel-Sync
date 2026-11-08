"""A business's KYC case: run the pipeline over its documents and decide.

process_case() is idempotent: documents already analysed keep their fields;
cross-document checks and the verdict are recomputed every time, so fixing
one document (re-upload) clears the problems it caused elsewhere.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, KycCheck, KycDocument, Order
from app.services import tracker
from app.services.kyc.identity import Check, gstin_checks, udyam_checks
from app.services.kyc.validators import (
    DOC_LABEL,
    DocAnalysis,
    analyse_document,
    cross_checks,
    required_docs,
    verdict,
)
from app.services.leads import lead_for_business
from app.services.storage import get_storage

log = logging.getLogger(__name__)


def identity_checks(biz: Business) -> list[Check]:
    checks: list[Check] = []
    if biz.gstin:
        checks += gstin_checks(biz.gstin)
    if biz.udyam_number:
        checks += udyam_checks(biz.udyam_number, biz.gstin)
    if not checks:
        checks.append(Check("registration", "review", "Add your GSTIN or Udyam number to continue"))
    return checks


def _analysis_from_row(doc: KycDocument) -> DocAnalysis | None:
    a = (doc.extracted or {}).get("analysis")
    if not a:
        return None
    return DocAnalysis(
        doc_type=doc.doc_type,
        fields=a.get("fields", {}),
        title=a.get("title"),
        sharpness=a.get("sharpness"),
        checks=[Check(**c) for c in a.get("checks", [])],
        readable=a.get("readable", True),
    )


def process_case(db: Session, business_id: int) -> str:
    biz = db.get(Business, business_id)
    docs = list(db.scalars(select(KycDocument).where(KycDocument.business_id == business_id)))
    storage = get_storage()
    analyses: dict[str, DocAnalysis] = {}
    for doc in docs:
        a = _analysis_from_row(doc)
        if a is None and doc.storage_key:
            try:
                a = analyse_document(doc.doc_type, storage.get(doc.storage_key))
            except Exception:  # noqa: BLE001 - a bad file must not break the case
                log.exception("KYC analysis failed for document %s", doc.id)
                a = DocAnalysis(
                    doc.doc_type,
                    checks=[Check("document_reading", "review", "Could not read this file automatically")],
                )
            doc.extracted = {
                **(doc.extracted or {}),
                "status": "done",
                "analysis": {
                    "fields": a.fields,
                    "title": a.title,
                    "sharpness": a.sharpness,
                    "readable": a.readable,
                    "checks": [c.as_dict() for c in a.checks],
                },
            }
        if a:
            analyses[doc.doc_type] = a

    cross = cross_checks(analyses, typed_gstin=biz.gstin)
    by_doc: dict[str, list[Check]] = {}
    for doc in docs:
        file_check = Check(
            "file_type", "pass", f"{doc.extracted.get('file_type')}, {doc.extracted.get('size')}"
        )
        checks = (
            [file_check, *analyses[doc.doc_type].checks, *cross.get(doc.doc_type, [])]
            if doc.doc_type in analyses
            else [file_check]
        )
        # A reviewer's decision on a check wins over the automatic result.
        for name, o in (doc.extracted or {}).get("overrides", {}).items():
            checks = [
                Check(c.name, o["result"], f"{c.reason} Reviewed by {o['by']}: {o['note']}")
                if c.name == name
                else c
                for c in checks
            ]
        by_doc[doc.doc_type] = checks
        for old in db.scalars(select(KycCheck).where(KycCheck.document_id == doc.id)):
            db.delete(old)
        db.flush()
        for c in checks:
            db.add(KycCheck(document_id=doc.id, check_name=c.name, result=c.result, reason=c.reason))

    by_doc["_identity"] = identity_checks(biz)
    result, _ = verdict(by_doc, required_docs(biz.gstin, biz.udyam_number))
    _on_verdict(db, biz, result)
    return result


def _on_verdict(db: Session, biz: Business, result: str) -> None:
    lead = lead_for_business(db, biz.id)
    if result == "pass":
        if lead:
            lead.stage, lead.stopped_at = "KYC complete", None
        order = db.scalar(
            select(Order)
            .where(Order.business_id == biz.id, Order.state == "order_placed")
            .order_by(Order.id.desc())
        )
        if order:
            tracker.set_state(db, order, "kyc_verified", actor="smart-kyc")
    elif lead and lead.stage == "Quote accepted":
        lead.stopped_at = "kyc"


def case_status(db: Session, biz: Business) -> dict:
    docs = list(db.scalars(select(KycDocument).where(KycDocument.business_id == biz.id)))
    views, by_doc = [], {}
    for doc in docs:
        checks = [
            Check(k.check_name, k.result, k.reason)
            for k in db.scalars(select(KycCheck).where(KycCheck.document_id == doc.id).order_by(KycCheck.id))
        ]
        processing = (doc.extracted or {}).get("status") == "processing"
        by_doc[doc.doc_type] = checks
        fails = [c for c in checks if c.result == "fail"]
        reviews = [c for c in checks if c.result == "review"]
        views.append(
            {
                "id": doc.id,
                "doc_type": doc.doc_type,
                "file": {k: doc.extracted.get(k) for k in ("file_type", "size")},
                "uploaded_at": doc.uploaded_at,
                "processing": processing,
                "result": "processing"
                if processing
                else "fail"
                if fails
                else "review"
                if reviews
                else "pass",
                "checks": [c.as_dict() for c in checks],
            }
        )
    identity = identity_checks(biz)
    required = required_docs(biz.gstin, biz.udyam_number)
    by_doc["_identity"] = identity
    overall, reasons = verdict(by_doc, required)
    if any(v["processing"] for v in views):
        overall = "processing"
    uploaded = {v["doc_type"] for v in views}
    return {
        "identity_checks": identity,
        "documents": views,
        "required": required,
        "missing": [d for d in required if d not in uploaded],
        "overall": overall,
        "reasons": reasons,
        "labels": DOC_LABEL,
    }
