import random

import pytest

from app.services.catalogue import SEGMENT_CODES, get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import build_tiers
from app.services.registry import gstin_is_active
from app.services.repair import ChangeRequest, analyse

CLINIC = BusinessProfile("prof", 1, 5, 1, True)
BASE = {"P01": 1, "P16": 3, "P20": 2}


def ids(option):
    return set(option.items)


def test_nothing_breaks_when_nothing_changes():
    r = analyse(BASE, CLINIC, ChangeRequest(budget=5000))
    assert r.problems == [] and r.recommended == "as_asked"


def test_budget_gap_is_explained_and_smallest_fix_found():
    r = analyse(BASE, CLINIC, ChangeRequest(budget=2200, add=frozenset({"P09"})))
    assert r.problems[0]["rule"] == "budget"
    assert "over your" in r.problems[0]["message"]
    rec = next(o for o in r.options if o.id == r.recommended)
    assert rec.fits_budget and "P09" in ids(rec)  # the thing they asked for stays
    assert len([c for c in rec.changes if c.rule == "budget"]) == 1


def test_essentials_that_dont_fit_produce_a_trade_off():
    r = analyse(
        BASE,
        CLINIC,
        ChangeRequest(budget=2000, add=frozenset({"P09"}), must_have=frozenset({"P09", "P16", "P20"})),
    )
    assert r.needs_choice and r.recommended is None
    kinds = {o.kind for o in r.options}
    assert {"keep_must_haves", "fit_budget"} <= kinds
    keep = next(o for o in r.options if o.kind == "keep_must_haves")
    fit = next(o for o in r.options if o.kind == "fit_budget")
    assert {"P09", "P16", "P20"} <= ids(keep) and not keep.fits_budget
    assert fit.fits_budget and fit.unmet  # says which essential it drops


def test_airfiber_breaks_backup_offers_alternative_and_handoff():
    r = analyse({**BASE, "P09": 1}, CLINIC, ChangeRequest(connection="P04", must_have=frozenset({"P09"})))
    assert any(p["rule"] == "requires_one_of" for p in r.problems)
    kinds = {o.kind: o for o in r.options}
    assert "P04" in ids(kinds["repaired"]) and "P09" not in ids(kinds["repaired"])
    assert "P09" in ids(kinds["alternative"])  # stay on fibre, backup keeps working
    assert kinds["handoff"].unmet == ["P09"]  # the need travels with the handoff


def test_losing_gst_swaps_to_nearest_eligible():
    r = analyse({"P02": 1, "P15": 1, "P16": 3}, CLINIC, ChangeRequest(gstin_active=False))
    rec = next(o for o in r.options if o.id == r.recommended)
    assert "P15" not in ids(rec) and "P18" in ids(rec)
    assert r.problems[0]["rule"] == "requires_gstin"


def test_moving_to_tier2_downgrades_1g():
    r = analyse({"P03": 1, "P16": 3}, CLINIC, ChangeRequest(city_tier=2))
    rec = next(o for o in r.options if o.id == r.recommended)
    assert "P03" not in ids(rec) and "P02" in ids(rec)


def test_more_sites_rescales_quantities():
    chain = BusinessProfile("multi", 1, 30, 3, True)
    r = analyse({"P02": 3, "P09": 3, "P23": 6}, chain, ChangeRequest(sites=5))
    rec = next(o for o in r.options if o.id == r.recommended)
    assert rec.items["P02"] == 5 and rec.items["P23"] == 10


def test_unknown_product_rejected():
    with pytest.raises(ValueError):
        analyse(BASE, CLINIC, ChangeRequest(add=frozenset({"P99"})))


def test_fuzz_no_option_is_ever_ineligible(leads):
    """Random leads x random changes: every returned option passes the rules engine,
    and a recommended option always fits the budget and keeps every essential."""
    rng = random.Random(7)
    catalogue = get_catalogue()
    primaries = ["P01", "P02", "P03", "P04", "P05", "P06"]
    for row in rng.sample(leads, 300):
        biz = BusinessProfile(
            SEGMENT_CODES[row["segment"]],
            int(row["city_tier"]),
            int(row["employee_count"]),
            int(row["num_sites"]),
            gstin_is_active(row["gstin"] or None),
        )
        tier = rng.choice(build_tiers(biz))
        current = {i.product_id: i.qty for i in tier.items}
        req = ChangeRequest(
            budget=rng.choice([None, int(tier.monthly_total * rng.uniform(0.6, 1.1))]),
            add=frozenset(rng.sample(sorted(catalogue), rng.randint(0, 2))),
            must_have=frozenset(rng.sample(sorted(current), min(len(current), rng.randint(0, 2)))),
            sites=rng.choice([None, rng.randint(1, 12)]),
            city_tier=rng.choice([None, 1, 2]),
            gstin_active=rng.choice([None, False]),
            connection=rng.choice([None, None, rng.choice(primaries)]),
        )
        changed = BusinessProfile(
            biz.segment,
            req.city_tier or biz.city_tier,
            biz.employees,
            req.sites or biz.sites,
            biz.gstin_active if req.gstin_active is None else req.gstin_active,
        )
        r = analyse(current, biz, req)
        had_connection = any(p in primaries for p in current)
        for o in r.options:
            if o.kind == "handoff":
                continue
            bad = [p for p in o.items if not eligible(catalogue[p], changed).ok]
            assert not bad, (row["lead_id"], o.id, bad)
            assert validate_bundle(o.items.keys()).ok, (row["lead_id"], o.id)
            if had_connection:
                assert any(p in primaries for p in o.items), (row["lead_id"], o.id, "lost its connection")
        if r.recommended:
            rec = next(o for o in r.options if o.id == r.recommended)
            assert rec.fits_budget and not rec.unmet


def test_new_connection_replaces_rather_than_stacks():
    small_town = BusinessProfile("prof", 1, 5, 1, True)
    r = analyse({"P02": 1, "P16": 3}, small_town, ChangeRequest(city_tier=2, add=frozenset({"P03"})))
    for o in r.options:
        if o.kind != "handoff":
            primaries = [p for p in o.items if p in {"P01", "P02", "P03", "P04", "P05", "P06"}]
            assert len(primaries) == 1, (o.id, o.items)


def test_budget_never_removes_the_only_connection():
    """8-person clinic asks for Internet Leased Line 100 (needs 25 staff) on a
    ₹5,000 budget. The fix may downgrade the line, but every option must still
    include a connection."""
    clinic = BusinessProfile("prof", 1, 8, 1, True)
    current = {"P02": 1, "P08": 3, "P16": 5, "P17": 1, "P20": 4}
    r = analyse(current, clinic, ChangeRequest(budget=5000, add=frozenset({"P06"})))
    primaries = {"P01", "P02", "P03", "P04", "P05", "P06"}
    for o in r.options:
        if o.kind != "handoff":
            assert primaries & set(o.items), (o.id, o.items)
    rec = next(o for o in r.options if o.id == r.recommended)
    assert rec.fits_budget
