from app.services.catalogue import get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.registry import gstin_is_active, gstin_registry

C = get_catalogue()
KIRANA = BusinessProfile(segment="micro", city_tier=2, employees=3, sites=1, gstin_active=False)
CHAIN = BusinessProfile(segment="multi", city_tier=1, employees=40, sites=5, gstin_active=True)


def test_catalogue_parsed():
    assert len(C) == 25
    assert C["P09"].requires_one_of == ("P01", "P02", "P03", "P05", "P06")
    assert C["P03"].tiers == (1,)
    assert C["P01"].segments == ("micro", "prof")


def test_tier_rule():
    r = eligible(C["P03"], KIRANA)
    assert not r.ok
    assert any("tier-1" in reason for reason in r.reasons)


def test_employee_and_site_minimums():
    assert not eligible(C["P05"], KIRANA).ok  # leased line needs 10 staff
    assert not eligible(C["P10"], BusinessProfile("multi", 1, 40, 2, True)).ok  # SD-WAN: 3 sites
    assert eligible(C["P10"], CHAIN).ok


def test_gstin_rule_needs_active_registration():
    assert not eligible(C["P15"], KIRANA).ok
    assert eligible(C["P15"], CHAIN).ok


def test_all_failures_reported_together():
    r = eligible(C["P10"], KIRANA)  # wrong size, sites and no GSTIN
    assert len(r.reasons) == 3


def test_cancelled_and_suspended_gstins_are_not_active():
    reg = gstin_registry()
    cancelled = next(g for g, r in reg.items() if r["status"] == "Cancelled")
    suspended = next(g for g, r in reg.items() if r["status"] == "Suspended")
    active = next(g for g, r in reg.items() if r["status"] == "Active")
    assert not gstin_is_active(cancelled)
    assert not gstin_is_active(suspended)
    assert gstin_is_active(active)
    assert not gstin_is_active(None)
    assert not gstin_is_active("27AAAAA0000A1Z5")  # not in registry


def test_dependencies():
    assert validate_bundle(["P01", "P09", "P23"]).ok
    bad = validate_bundle(["P07", "P09"])  # failover without a fixed line
    assert not bad.ok
    assert bad.violations[0].product_id == "P09"
    # CCTV accepts 5G AirFiber; failover does not.
    assert validate_bundle(["P04", "P23"]).ok
    assert not validate_bundle(["P04", "P09"]).ok
