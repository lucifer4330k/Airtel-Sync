from app.services.catalogue import SEGMENT_CODES, get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import build_tiers, price_bundle, quantity_for
from app.services.registry import gstin_is_active

C = get_catalogue()


def profile_from_lead(row: dict[str, str]) -> BusinessProfile:
    return BusinessProfile(
        segment=SEGMENT_CODES[row["segment"]],
        city_tier=int(row["city_tier"]),
        employees=int(row["employee_count"]),
        sites=int(row["num_sites"]),
        gstin_active=gstin_is_active(row["gstin"] or None),
    )


def test_no_lead_ever_gets_an_ineligible_or_broken_bundle(leads):
    """The guarantee the judges test: never recommend an ineligible product."""
    assert len(leads) == 5000
    for row in leads:
        biz = profile_from_lead(row)
        tiers = build_tiers(biz)
        assert tiers, f"{row['lead_id']} got no bundle"
        for b in tiers:
            ids = [i.product_id for i in b.items]
            bad = [pid for pid in ids if not eligible(C[pid], biz).ok]
            assert not bad, f"{row['lead_id']} {b.tier}: ineligible {bad}"
            assert validate_bundle(ids).ok, f"{row['lead_id']} {b.tier}: broken deps {ids}"


def test_tiers_are_deterministic(leads):
    biz = profile_from_lead(leads[0])
    assert build_tiers(biz) == build_tiers(biz)


def test_bundle_totals():
    biz = BusinessProfile("multi", 1, 30, 4, True)
    b = price_bundle({"P02": 4, "P09": 4, "P10": 4}, biz)
    assert b.contract_months == 24  # longest: SD-WAN
    assert b.eta_days == 14  # slowest: SD-WAN
    assert b.setup_total == 4 * 1500 + 4 * 5000
    low = sum(C[p].price_min * 4 for p in ("P02", "P09", "P10"))
    high = sum(C[p].price_max * 4 for p in ("P02", "P09", "P10"))
    assert low <= b.monthly_total <= high


def test_quantities_follow_profile():
    biz = BusinessProfile("multi", 1, 30, 4, True)
    assert quantity_for(C["P02"], biz) == 4  # per site
    assert quantity_for(C["P23"], biz) == 8  # 2 cameras per site
    assert quantity_for(C["P13"], biz) == 1  # one toll-free number
    assert quantity_for(C["P16"], biz) == 18  # email for ~60% of staff


def test_tier2_kirana_without_gstin():
    biz = BusinessProfile("micro", 2, 3, 1, False)
    ids = {i.product_id for b in build_tiers(biz) for i in b.items}
    assert "P15" not in ids  # WhatsApp API needs GSTIN
    assert "P03" not in ids  # 1G fibre is tier-1 only
    assert {"P01", "P07"} <= ids


def test_small_manufacturer_falls_back_from_leased_line():
    biz = BusinessProfile("mfg", 2, 8, 1, True)  # too small for P05, tier 2 blocks P03
    good = build_tiers(biz)[0]
    assert {i.product_id for i in good.items} & {"P02", "P01"}
