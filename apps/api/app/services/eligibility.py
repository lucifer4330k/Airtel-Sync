"""Deterministic eligibility rules over the catalogue.

The LLM never decides eligibility. It may only present products this module
returned as eligible, and the server re-validates anything it outputs.
"""

from dataclasses import dataclass, field

from app.services.catalogue import Product, get_catalogue


@dataclass(frozen=True)
class BusinessProfile:
    segment: str  # micro / prof / multi / mfg
    city_tier: int  # 1 or 2
    employees: int
    sites: int
    # True only when the business has a GSTIN that is format-valid AND Active
    # in the registry. "Has a GSTIN" is not enough.
    gstin_active: bool = False


@dataclass(frozen=True)
class Eligibility:
    product_id: str
    ok: bool
    reasons: tuple[str, ...] = ()


def eligible(product: Product, biz: BusinessProfile) -> Eligibility:
    """Pass/fail plus plain-language reasons for every rule that fails."""
    reasons: list[str] = []
    if biz.city_tier not in product.tiers:
        tiers = " or ".join(f"tier-{t}" for t in product.tiers)
        reasons.append(f"{product.name} is only sold in {tiers} cities")
    if biz.employees < product.min_employees:
        reasons.append(f"{product.name} needs at least {product.min_employees} employees")
    if biz.sites < product.min_sites:
        reasons.append(f"{product.name} needs at least {product.min_sites} sites")
    if product.requires_gstin and not biz.gstin_active:
        reasons.append(f"{product.name} needs an active GST registration")
    return Eligibility(product.product_id, ok=not reasons, reasons=tuple(reasons))


def eligible_products(biz: BusinessProfile) -> list[Product]:
    return [p for p in get_catalogue().values() if eligible(p, biz).ok]


@dataclass
class BundleViolation:
    product_id: str
    needs_one_of: tuple[str, ...]
    message: str


@dataclass
class BundleCheck:
    ok: bool
    violations: list[BundleViolation] = field(default_factory=list)


def validate_bundle(product_ids: list[str] | set[str]) -> BundleCheck:
    """Every product with requires_one_of needs one of those in the same bundle."""
    catalogue = get_catalogue()
    ids = set(product_ids)
    violations = []
    for pid in sorted(ids):
        deps = catalogue[pid].requires_one_of
        if deps and not ids.intersection(deps):
            dep_names = ", ".join(catalogue[d].name for d in deps)
            violations.append(
                BundleViolation(
                    product_id=pid,
                    needs_one_of=deps,
                    message=f"{catalogue[pid].name} needs an internet line first ({dep_names})",
                )
            )
    return BundleCheck(ok=not violations, violations=violations)
