"""Generate the judge scorecard (apps/api/app/services/scorecard.json).

Run from apps/api with the dev database up (takes ~3 minutes, mostly OCR):
    uv run python ../../scripts/scorecard.py

Measures the prototype, separately from any projected business impact:
  1. Lead sweep: Good/Better/Best for all 5,000 lead profiles; count any
     ineligible product or broken dependency.
  2. Advisor personas: every scripted persona through the real advisor
     engine (inside a transaction that is rolled back).
  3. Quote repair fuzz: 1,000 random leads x random changes; count invalid
     options, and how often a valid fix within budget was found when the
     brute-force search says one exists.
  4. KYC answer key: K01-K12 through OCR and every check.
"""

import csv
import json
import random
import sys
import time
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "apps" / "api") if (_root / "apps" / "api").exists() else str(_root))

import yaml  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.catalogue import SEGMENT_CODES, get_catalogue  # noqa: E402
from app.services.eligibility import BusinessProfile, eligible, validate_bundle  # noqa: E402
from app.services.pricing import build_tiers, price_bundle  # noqa: E402
from app.services.registry import gstin_is_active, gstin_registry  # noqa: E402
from app.services.repair import PRIMARY, ChangeRequest, analyse  # noqa: E402

OUT = _root / "apps" / "api" / "app" / "services" / "scorecard.json"


def leads() -> list[dict]:
    with (get_settings().data_dir / "smb_leads.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def profile(row) -> BusinessProfile:
    return BusinessProfile(
        SEGMENT_CODES[row["segment"]],
        int(row["city_tier"]),
        int(row["employee_count"]),
        int(row["num_sites"]),
        gstin_is_active(row["gstin"] or None),
    )


def lead_sweep(rows) -> dict:
    catalogue = get_catalogue()
    tiers = ineligible = broken = 0
    for row in rows:
        biz = profile(row)
        for b in build_tiers(biz):
            tiers += 1
            ids = [i.product_id for i in b.items]
            ineligible += any(not eligible(catalogue[p], biz).ok for p in ids)
            broken += not validate_bundle(ids).ok
    return {
        "profiles": len(rows),
        "plans_checked": tiers,
        "ineligible_plans": ineligible,
        "broken_dependencies": broken,
    }


def personas() -> dict:
    from app.db import SessionLocal
    from app.models import Business, Lead
    from app.services.advisor import engine
    from app.services.quotes import _items, profile_of

    reg = gstin_registry()
    subs = {
        "{ACTIVE_GSTIN}": next(g for g, r in reg.items() if r["status"] == "Active"),
        "{CANCELLED_GSTIN}": next(g for g, r in reg.items() if r["status"] == "Cancelled"),
    }

    def sub(t):
        for k, v in subs.items():
            t = t.replace(k, v)
        return t

    files = sorted((_root / "apps" / "api" / "tests" / "advisor_scenarios").glob("*.yaml"))
    cases = [p for f in files for p in yaml.safe_load(f.read_text("utf-8"))]
    catalogue = get_catalogue()
    results = []
    with SessionLocal() as db:
        db.begin()
        try:
            for case in cases:
                session, _ = engine.start(db, "web", None)
                turns = [engine.handle(db, session, sub(case["open"]))]
                db.flush()
                for _ in range(10):
                    last = turns[-1]
                    if last.get("done") or last.get("needs_human"):
                        break
                    answer = case.get("answers", {}).get((session.slots or {}).get("awaiting"))
                    if answer is None:
                        break
                    turns.append(engine.handle(db, session, sub(answer)))
                    db.flush()
                card = next((t["bundle"] for t in reversed(turns) if t.get("bundle")), None)
                replies = "\n".join(t["reply"] for t in turns)
                ok, why = True, []
                if case.get("note") and case["note"] not in replies:
                    ok, why = False, why + ["missing explanation"]
                if case.get("needs_human") is not None:
                    flagged = any(t.get("needs_human") for t in turns)
                    if card and not flagged:
                        lead = db.query(Lead).filter(Lead.business_id == card["business_id"]).first()
                        flagged = bool(lead and lead.needs_human)
                    if flagged != case["needs_human"]:
                        ok, why = False, why + ["specialist flag"]
                if card:
                    biz = db.get(Business, card["business_id"])
                    prof = profile_of(biz)
                    from app.models import Quote

                    for q in card["quotes"]:
                        ids = [i.product_id for i in _items(db, db.get(Quote, q["id"]))]
                        if (
                            any(not eligible(catalogue[p], prof).ok for p in ids)
                            or not validate_bundle(ids).ok
                        ):
                            ok, why = False, why + ["ineligible product"]
                        if set(case.get("never", [])) & set(ids):
                            ok, why = False, why + ["forbidden product"]
                    rec = [i.product_id for i in _items(db, db.get(Quote, card["recommended_quote_id"]))]
                    if not set(case.get("include", [])) <= set(rec):
                        ok, why = False, why + ["missing product"]
                    if case.get("segment") and biz.segment != case["segment"]:
                        ok, why = False, why + ["wrong segment"]
                elif case.get("include"):
                    ok, why = False, why + ["no plan"]
                results.append({"id": case["id"], "ok": ok, "turns": len(turns), "issues": why})
        finally:
            db.rollback()
    return {
        "total": len(results),
        "passed": sum(r["ok"] for r in results),
        "max_turns": max(r["turns"] for r in results),
        "failures": [r for r in results if not r["ok"]],
    }


def repair_fuzz(rows, n=1000) -> dict:
    rng = random.Random(2026)
    catalogue = get_catalogue()
    invalid = found = solvable = handoffs = 0
    for row in rng.sample(rows, n):
        biz = profile(row)
        tier = rng.choice(build_tiers(biz))
        current = {i.product_id: i.qty for i in tier.items}
        budget = int(tier.monthly_total * rng.uniform(0.6, 1.0))
        req = ChangeRequest(
            budget=budget,
            add=frozenset(rng.sample(sorted(catalogue), rng.randint(0, 1))),
            sites=rng.choice([None, rng.randint(1, 12)]),
            city_tier=rng.choice([None, 1, 2]),
        )
        r = analyse(current, biz, req)
        changed = BusinessProfile(
            biz.segment,
            req.city_tier or biz.city_tier,
            biz.employees,
            req.sites or biz.sites,
            biz.gstin_active,
        )
        for o in r.options:
            if o.kind != "handoff" and (
                any(not eligible(catalogue[p], changed).ok for p in o.items)
                or not validate_bundle(o.items).ok
            ):
                invalid += 1
        handoffs += any(o.kind == "handoff" for o in r.options)
        # Does ANY valid non-empty subset of the repaired bundle fit the budget? (brute force)
        # A subset without a connection doesn't count when the plan had one:
        # "keep only the mobile lines" isn't a fix for an internet plan.
        base = next((o for o in r.options if o.kind in ("repaired", "keep_must_haves")), None)
        if base and base.items:
            # must keep what the owner explicitly added
            keep = [p for p in req.add if p in base.items]
            rest = sorted(set(base.items) - set(keep))
            had_connection = any(p in PRIMARY for p in current)
            exists = any(
                validate_bundle([*keep, *sub]).ok
                and (not had_connection or any(p in PRIMARY for p in [*keep, *sub]))
                and price_bundle({p: base.items[p] for p in [*keep, *sub]}, changed).monthly_total <= budget
                for k in range(0 if keep else 1, len(rest) + 1)
                for sub in combinations(rest, k)
            )
            if exists:
                solvable += 1
                found += any(o.fits_budget and o.kind != "handoff" for o in r.options)
    return {
        "cases": n,
        "invalid_options": invalid,
        "solvable_within_budget": solvable,
        "valid_fix_found": found,
        "handoffs_offered": handoffs,
    }


def kyc() -> dict:
    from app.services.kyc.answer_key import ANSWER_KEY, evaluate

    rows = []
    for applicant, (expected, phrase, finding) in sorted(ANSWER_KEY.items()):
        actual, reasons = evaluate(applicant)
        rows.append(
            {
                "applicant": applicant,
                "finding": finding,
                "expected": expected,
                "actual": actual,
                "reason": reasons[0] if reasons else "",
                "ok": actual == expected and (phrase is None or any(phrase in r for r in reasons)),
            }
        )
    return {"applicants": rows, "correct": sum(r["ok"] for r in rows), "total": len(rows)}


def main() -> None:
    t0 = time.time()
    rows = leads()
    card = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds")}
    print("lead sweep…")
    card["lead_sweep"] = lead_sweep(rows)
    print("advisor personas…")
    card["personas"] = personas()
    print("repair fuzz…")
    card["repair"] = repair_fuzz(rows)
    print("KYC answer key (OCR)…")
    card["kyc"] = kyc()
    card["seconds"] = round(time.time() - t0)
    OUT.write_text(json.dumps(card, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in card.items() if k != "kyc"}, indent=1))
    print(f"KYC {card['kyc']['correct']}/{card['kyc']['total']} -> {OUT}")


if __name__ == "__main__":
    main()
