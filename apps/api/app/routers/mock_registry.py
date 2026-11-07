"""Mocked government lookups. Shaped like a real registry API, with latency."""

import asyncio
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.kyc.gstin_checksum import validate_gstin
from app.services.registry import lookup_gstin, lookup_udyam

router = APIRouter(prefix="/mock", tags=["mock registries"])


class GstinRecord(BaseModel):
    gstin: str
    legal_name: str
    trade_name: str
    constitution: str
    address: str
    state: str
    registration_date: str
    status: str  # Active / Cancelled / Suspended


class UdyamRecord(BaseModel):
    udyam_number: str
    enterprise_name: str
    enterprise_type: str
    major_activity: str
    nic_description: str
    state: str
    city: str
    date_of_registration: str


async def _latency() -> None:
    s = get_settings()
    await asyncio.sleep(
        random.uniform(s.mock_registry_min_delay_ms, s.mock_registry_max_delay_ms) / 1000
    )


@router.get("/gstin/{gstin}", response_model=GstinRecord)
async def get_gstin(gstin: str) -> GstinRecord:
    await _latency()
    check = validate_gstin(gstin)
    if not check.ok:
        raise HTTPException(status_code=422, detail=check.reason)
    rec = lookup_gstin(gstin)
    if rec is None:
        raise HTTPException(status_code=404, detail="GSTIN not found in registry")
    return GstinRecord(
        gstin=rec["gstin"],
        legal_name=rec["legal_name"],
        trade_name=rec["trade_name"],
        constitution=rec["constitution"],
        address=rec["principal_place_of_business"],
        state=rec["state"],
        registration_date=rec["registration_date"],
        status=rec["status"],
    )


@router.get("/udyam/{number}", response_model=UdyamRecord)
async def get_udyam(number: str) -> UdyamRecord:
    await _latency()
    rec = lookup_udyam(number)
    if rec is None:
        raise HTTPException(status_code=404, detail="Udyam number not found in registry")
    return UdyamRecord(**rec)
