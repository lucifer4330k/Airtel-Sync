"""Smart KYC: consent -> identity (GSTIN / Udyam) -> document uploads -> status.

Until OTP login lands, every call about a case carries the X-KYC-Token issued
at consent; business ids alone are never enough.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.deps import owner_token
from app.core.logging import mask_pii
from app.core.ratelimit import limit
from app.core.security import kyc_token, verify_kyc_token
from app.db import get_db
from app.models import AuditLog, Business, Consent, KycDocument
from app.services.catalogue import SEGMENT_CODES
from app.services.kyc import jobs
from app.services.kyc.case import case_status, identity_checks, process_case
from app.services.kyc.identity import gstin_checks, overall, udyam_checks
from app.services.kyc.upload import MAX_BYTES, human_size, sniff
from app.services.registry import lookup_gstin, lookup_udyam
from app.services.storage import get_storage

router = APIRouter(prefix="/kyc", tags=["kyc"])

DocType = Literal["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]
CONSENT_TEXT_VERSION = "kyc-consent-v1"

# --- helpers -------------------------------------------------------------------


def _business(db: Session, business_id: int, token: str | None) -> Business:
    # Same 404 for "no such case" and "wrong token", so ids can't be probed.
    biz = db.get(Business, business_id)
    if biz is None or not verify_kyc_token(business_id, token):
        raise HTTPException(404, "KYC case not found")
    return biz


def _active_consent(db: Session, business_id: int, purpose: str) -> Consent | None:
    return db.scalar(
        select(Consent)
        .where(Consent.business_id == business_id, Consent.purpose == purpose, Consent.withdrawn_at.is_(None))
        .order_by(Consent.granted_at.desc())
    )


def _drop_document(db: Session, doc: KycDocument) -> str | None:
    """Deletes the row; returns the storage key to delete once the commit succeeds."""
    db.delete(doc)
    return doc.storage_key


def _delete_objects(keys: list[str | None]) -> None:
    storage = get_storage()
    for key in filter(None, keys):
        storage.delete(key)


# --- schemas -------------------------------------------------------------------


class ProfileIn(BaseModel):
    segment: str
    city_tier: int = Field(ge=1, le=2)
    employees: int = Field(ge=1)
    sites: int = Field(ge=1)


class ConsentIn(BaseModel):
    kyc: bool
    marketing: bool = False
    text_version: str = CONSENT_TEXT_VERSION
    language: str | None = None
    # Either an existing business (from checkout, with its owner token) or a profile.
    business_id: int | None = None
    profile: ProfileIn | None = None


class IdentityIn(BaseModel):
    gstin: str | None = Field(None, max_length=15)
    udyam_number: str | None = Field(None, max_length=19)


class WithdrawIn(BaseModel):
    purpose: Literal["kyc", "marketing"]


# --- endpoints -----------------------------------------------------------------


@router.post("/consent", status_code=201)
def give_consent(
    body: ConsentIn,
    db: Annotated[Session, Depends(get_db)],
    x_kyc_token: Annotated[str | None, Depends(owner_token)] = None,
):
    """Opens a KYC case. Consent is recorded before anything is collected."""
    if not body.kyc:
        raise HTTPException(422, "KYC consent is required to verify your business")
    if body.business_id is not None:
        biz = _business(db, body.business_id, x_kyc_token)
    elif body.profile is not None:
        segment = SEGMENT_CODES.get(body.profile.segment, body.profile.segment)
        if segment not in {"micro", "prof", "multi", "mfg"}:
            raise HTTPException(422, f"Unknown segment '{body.profile.segment}'")
        biz = Business(
            segment=segment,
            tier=body.profile.city_tier,
            employees=body.profile.employees,
            sites=body.profile.sites,
            language=body.language,
        )
        db.add(biz)
        db.flush()
    else:
        raise HTTPException(422, "Pass business_id (with its token) or a profile")
    db.add(Consent(business_id=biz.id, purpose="kyc", text_version=body.text_version))
    if body.marketing:
        db.add(Consent(business_id=biz.id, purpose="marketing", text_version=body.text_version))
    db.commit()
    return {"business_id": biz.id, "token": kyc_token(biz.id)}


@router.post("/{business_id}/consent/withdraw")
def withdraw_consent(
    business_id: int,
    body: WithdrawIn,
    db: Annotated[Session, Depends(get_db)],
    x_kyc_token: Annotated[str | None, Depends(owner_token)] = None,
):
    """Withdrawing KYC consent deletes every uploaded document immediately."""
    _business(db, business_id, x_kyc_token)
    consent = _active_consent(db, business_id, body.purpose)
    if consent is None:
        raise HTTPException(404, f"No active {body.purpose} consent")
    consent.withdrawn_at = datetime.now(UTC)
    keys: list[str | None] = []
    if body.purpose == "kyc":
        for doc in db.scalars(select(KycDocument).where(KycDocument.business_id == business_id)):
            keys.append(_drop_document(db, doc))
    db.commit()
    _delete_objects(keys)
    return {"withdrawn": body.purpose, "documents_deleted": len(keys)}


@router.get("/lookup", dependencies=[Depends(limit(30, 60))])
def lookup(gstin: str | None = Query(None, max_length=15), udyam: str | None = Query(None, max_length=19)):
    """Registry auto-fill. Exactly one of gstin / udyam."""
    if bool(gstin) == bool(udyam):
        raise HTTPException(422, "Pass exactly one of gstin or udyam")
    if gstin:
        rec = lookup_gstin(gstin)
        return {
            "kind": "gstin",
            "checks": [c.as_dict() for c in gstin_checks(gstin)],
            "record": rec
            and {
                "legal_name": rec["legal_name"],
                "trade_name": rec["trade_name"],
                "address": rec["principal_place_of_business"],
                "state": rec["state"],
                "status": rec["status"],
            },
        }
    rec = lookup_udyam(udyam)
    return {
        "kind": "udyam",
        "checks": [c.as_dict() for c in udyam_checks(udyam, None)],
        "record": rec
        and {
            "legal_name": rec["enterprise_name"],
            "trade_name": rec["enterprise_name"],
            "address": f"{rec['city']}, {rec['state']}",
            "state": rec["state"],
            "status": "Registered",
        },
    }


@router.put("/{business_id}/identity")
def set_identity(
    business_id: int,
    body: IdentityIn,
    db: Annotated[Session, Depends(get_db)],
    x_kyc_token: Annotated[str | None, Depends(owner_token)] = None,
):
    biz = _business(db, business_id, x_kyc_token)
    if _active_consent(db, business_id, "kyc") is None:
        raise HTTPException(403, "KYC consent was withdrawn")
    # A blank field keeps what is already on file (e.g. the GSTIN given to the
    # advisor); it never silently erases a registration.
    gstin = (body.gstin or "").strip().upper() or biz.gstin
    udyam = (body.udyam_number or "").strip().upper() or biz.udyam_number
    if not gstin and not udyam:
        raise HTTPException(422, "Enter a GSTIN or a Udyam number")

    biz.gstin, biz.udyam_number = gstin, udyam
    if gstin and (rec := lookup_gstin(gstin)):
        biz.name, biz.state = rec["legal_name"], rec["state"]
    if udyam and (rec := lookup_udyam(udyam)):
        biz.name = biz.name or rec["enterprise_name"]
        biz.type, biz.city, biz.state = rec["nic_description"], rec["city"], biz.state or rec["state"]
    db.commit()
    process_case(db, business_id)  # cached analyses: cheap; re-runs cross-checks with the new GSTIN
    db.commit()
    checks = identity_checks(biz)
    return {"name": biz.name, "result": overall(checks), "checks": [c.as_dict() for c in checks]}


@router.post("/documents", status_code=201, dependencies=[Depends(limit(20, 60))])
async def upload_document(
    db: Annotated[Session, Depends(get_db)],
    business_id: Annotated[int, Form()],
    doc_type: Annotated[DocType, Form()],
    file: Annotated[UploadFile, File()],
    background: BackgroundTasks,
    x_kyc_token: Annotated[str | None, Depends(owner_token)] = None,
):
    _business(db, business_id, x_kyc_token)
    if _active_consent(db, business_id, "kyc") is None:
        raise HTTPException(403, "KYC consent was withdrawn")

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 5 MB. Take a smaller photo or scan and try again.")
    if not data:
        raise HTTPException(422, "The file is empty")
    kind = sniff(data)
    if kind is None:
        raise HTTPException(415, "Upload a JPEG, PNG or PDF. Other file types are not accepted.")

    # One current document per type: a re-upload replaces the old one.
    old_keys = [
        _drop_document(db, old)
        for old in db.scalars(
            select(KycDocument).where(
                KycDocument.business_id == business_id, KycDocument.doc_type == doc_type
            )
        )
    ]

    key = f"kyc/{business_id}/{uuid.uuid4().hex}.{kind.ext}"
    get_storage().put(key, data)  # encrypted before it leaves the API
    retention = get_settings().document_retention_days
    doc = KycDocument(
        business_id=business_id,
        doc_type=doc_type,
        storage_key=key,
        extracted={"file_type": kind.label, "size": human_size(len(data)), "status": "processing"},
        purge_after=datetime.now(UTC).date() + timedelta(days=retention),
    )
    db.add(doc)
    try:
        db.commit()
    except Exception:
        get_storage().delete(key)  # don't leave an orphaned image behind
        raise
    _delete_objects(old_keys)
    db.refresh(doc)
    jobs.dispatch(background, business_id, sessionmaker(bind=db.get_bind(), expire_on_commit=False))
    return {
        "id": doc.id,
        "doc_type": doc.doc_type,
        "file": {"file_type": kind.label, "size": human_size(len(data))},
        "uploaded_at": doc.uploaded_at,
        "processing": True,
        "result": "processing",
        "checks": [],
    }


@router.get("/{business_id}/documents/{document_id}/file")
def download_document(
    business_id: int,
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    x_kyc_token: Annotated[str | None, Depends(owner_token)] = None,
):
    """The owner re-opens their own upload. Decrypted in memory; every view is audit-logged."""
    _business(db, business_id, x_kyc_token)
    doc = db.get(KycDocument, document_id)
    if doc is None or doc.business_id != business_id or not doc.storage_key:
        raise HTTPException(404, "Document not found")
    data = get_storage().get(doc.storage_key)
    kind = sniff(data)
    db.add(AuditLog(actor=f"owner:{business_id}", event="kyc.document_view", target=f"kyc_document:{doc.id}"))
    db.commit()
    return Response(
        content=data,
        media_type=kind.mime if kind else "application/octet-stream",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{business_id}/status")
def kyc_status(
    business_id: int,
    db: Annotated[Session, Depends(get_db)],
    x_kyc_token: Annotated[str | None, Depends(owner_token)] = None,
):
    biz = _business(db, business_id, x_kyc_token)
    st = case_status(db, biz)
    identity = st.pop("identity_checks")
    return {
        "business_id": business_id,
        "name": biz.name,
        "gstin": biz.gstin and mask_pii(biz.gstin),
        "udyam_number": biz.udyam_number and mask_pii(biz.udyam_number),
        "identity": {"result": overall(identity), "checks": [c.as_dict() for c in identity]},
        **st,
        "consent": {
            "kyc": _active_consent(db, business_id, "kyc") is not None,
            "marketing": _active_consent(db, business_id, "marketing") is not None,
        },
    }
