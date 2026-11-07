"""Bundle building and pricing: Good / Better / Best per segment.

Quantity rules and templates were derived from the 368 activated bundles in
smb_leads.csv (e.g. fibre and failover are bought one per site, mobile lines
at roughly one per three staff, cameras at about two per site).
"""

import math
from dataclasses import dataclass

from app.services.catalogue import Product, get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle

# --- quantities --------------------------------------------------------------


def quantity_for(product: Product, biz: BusinessProfile) -> int:
    """How many units of a product this business needs."""
    e, s = biz.employees, biz.sites
    pid = product.product_id
    if pid == "P24":  # machine sensors: about one per ten staff on the floor
        return max(2, math.ceil(e / 10))
    if pid == "P25":  # fleet trackers: about one vehicle per site
        return max(1, s)
    match product.unit:
        case "per site" | "per counter":
            return s
        case "per line":
            return min(max(1, math.ceil(e / 3)), 3 * s + 7)
        case "per user":
            return max(1, math.ceil(e * 0.6))
        case "per device":
            return max(1, math.ceil(e * 0.4))
        case "per camera":
            return 2 * s
        case "per channel":
            return max(2, math.ceil(e / 4))
        case _:  # per IP / account / number / pack
            return 1


# --- unit price within the catalogue range ------------------------------------


def unit_price(product: Product, biz: BusinessProfile, qty: int) -> int:
    """Monthly price for ONE unit, somewhere in [price_min, price_max].

    TODO(Debanjan): pick the pricing policy. See the note in the chat.
    """
    return product.price_min


# --- bundles -----------------------------------------------------------------


@dataclass
class LineItem:
    product_id: str
    name: str
    unit: str
    qty: int
    unit_price: int
    monthly: int
    setup: int
    is_addon: bool = False


@dataclass
class PricedBundle:
    tier: str
    items: list[LineItem]
    monthly_total: int
    setup_total: int
    contract_months: int
    eta_days: int


def price_bundle(
    quantities: dict[str, int], biz: BusinessProfile, tier: str = "custom",
    addons: frozenset[str] = frozenset(),
) -> PricedBundle:
    catalogue = get_catalogue()
    items = []
    for pid, qty in quantities.items():
        p = catalogue[pid]
        up = unit_price(p, biz, qty)
        # Setup fee is charged per unit (matches all 368 activated bundles).
        setup = p.setup_fee * qty
        items.append(LineItem(pid, p.name, p.unit, qty, up, up * qty, setup, pid in addons))
    products = [catalogue[i.product_id] for i in items]
    return PricedBundle(
        tier=tier,
        items=items,
        monthly_total=sum(i.monthly for i in items),
        setup_total=sum(i.setup for i in items),
        contract_months=max((p.min_contract_months for p in products), default=0),
        eta_days=max((p.install_days for p in products), default=0),
    )


# Each slot is an ordered list of alternatives: the first eligible one wins.
Slot = tuple[str, ...]
FIBRE: Slot = ("P02", "P01", "P04")

TEMPLATES: dict[str, dict[str, list[Slot]]] = {
    "micro": {
        "good": [("P01", "P04"), ("P07",)],
        "better": [("P01", "P04"), ("P07",), ("P19",), ("P22",)],
        "best": [("P02", "P01", "P04"), ("P07",), ("P19",), ("P22",), ("P23",), ("P15",)],
    },
    "prof": {
        "good": [FIBRE, ("P07",), ("P16",)],
        "better": [FIBRE, ("P08", "P07"), ("P16",), ("P17",), ("P20",)],
        "best": [("P03",) + FIBRE, ("P08", "P07"), ("P16",), ("P17",), ("P20",), ("P09",),
                 ("P12",)],
    },
    "multi": {
        "good": [("P01",), ("P08", "P07"), ("P09",)],
        "better": [FIBRE, ("P08", "P07"), ("P09",), ("P19",), ("P22",), ("P23",)],
        "best": [FIBRE, ("P08", "P07"), ("P09",), ("P10",), ("P19",), ("P22",), ("P23",),
                 ("P15",), ("P13",)],
    },
    "mfg": {
        "good": [("P03",) + FIBRE, ("P08", "P07"), ("P16",)],
        "better": [("P05", "P03") + FIBRE, ("P08", "P07"), ("P16",), ("P20",), ("P11",)],
        "best": [("P05", "P03") + FIBRE, ("P08", "P07"), ("P16",), ("P20",), ("P21",),
                 ("P23",), ("P24",), ("P09",)],
    },
}


def fill_template(slots: list[Slot], biz: BusinessProfile) -> dict[str, int]:
    """Pick the first eligible product per slot, then drop dependency orphans."""
    catalogue = get_catalogue()
    chosen: dict[str, int] = {}
    for slot in slots:
        for pid in slot:
            p = catalogue[pid]
            if eligible(p, biz).ok:
                chosen[pid] = quantity_for(p, biz)
                break
    # A dependant whose connectivity got dropped as ineligible must go too.
    check = validate_bundle(chosen.keys())
    for v in check.violations:
        chosen.pop(v.product_id, None)
    return chosen


def build_tiers(biz: BusinessProfile) -> list[PricedBundle]:
    """Good / Better / Best for this business, de-duplicated."""
    bundles: list[PricedBundle] = []
    seen: set[tuple] = set()
    for tier, slots in TEMPLATES[biz.segment].items():
        qty = fill_template(slots, biz)
        key = tuple(sorted(qty.items()))
        if qty and key not in seen:
            seen.add(key)
            bundles.append(price_bundle(qty, biz, tier))
    return bundles
