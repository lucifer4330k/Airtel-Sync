"""Quote building over the rules engine.

POST /quotes/preview is stateless (no DB): it returns Good / Better / Best for
a profile. Persisted quotes (POST /quotes, PATCH /quotes/{id}/items) come next.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.catalogue import SEGMENT_CODES, get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import build_tiers, price_bundle
from app.services.registry import gstin_is_active

router = APIRouter(prefix="/quotes", tags=["quotes"])


class ProfileIn(BaseModel):
    segment: str = Field(description="micro / prof / multi / mfg, or the lead-data segment name")
    city_tier: int = Field(ge=1, le=2)
    employees: int = Field(ge=1)
    sites: int = Field(ge=1)
    gstin: str | None = None

    def to_profile(self) -> BusinessProfile:
        seg = SEGMENT_CODES.get(self.segment, self.segment)
        if seg not in {"micro", "prof", "multi", "mfg"}:
            raise HTTPException(422, f"Unknown segment '{self.segment}'")
        return BusinessProfile(
            segment=seg,
            city_tier=self.city_tier,
            employees=self.employees,
            sites=self.sites,
            gstin_active=gstin_is_active(self.gstin),
        )


class CustomBundleIn(BaseModel):
    profile: ProfileIn
    items: dict[str, int] = Field(description="product_id -> quantity")


@router.post("/preview")
def preview(profile: ProfileIn):
    biz = profile.to_profile()
    return {"gstin_active": biz.gstin_active, "tiers": build_tiers(biz)}


@router.post("/price")
def price_custom(body: CustomBundleIn):
    """Price an arbitrary bundle, refusing ineligible items and broken dependencies."""
    biz = body.profile.to_profile()
    catalogue = get_catalogue()
    unknown = [pid for pid in body.items if pid not in catalogue]
    if unknown:
        raise HTTPException(422, f"Unknown products: {', '.join(unknown)}")
    problems = [r for pid in body.items for r in eligible(catalogue[pid], biz).reasons]
    problems += [v.message for v in validate_bundle(body.items.keys()).violations]
    if problems:
        raise HTTPException(422, {"reasons": problems})
    return price_bundle(body.items, biz)
