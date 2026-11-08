"""Quote repair: when the owner's budget or needs change, find the smallest
valid change instead of starting over.

    analyse(items, profile, change) -> RepairResult

1. Apply what the owner changed (sites, city, GST, chosen connection,
   added or removed services, budget, must-haves).
2. Say exactly what broke and which rule broke it.
3. Repair in order: eligibility (swap to the nearest eligible product, else
   drop), dependencies (bring in or swap the base connection), quantities.
4. If over budget, search small sets of moves (drop or downgrade optional
   items, never must-haves) for the fewest changes that fit.
5. If nothing keeps every must-have within budget, return the trade-off
   (keep must-haves vs. fit budget) for the owner to choose; if the chosen
   connection can't support a need, offer a site-assessment handoff that
   carries the need along.

Every option is re-validated by the rules engine before it is returned, so
an option can never contain an ineligible product or a broken dependency.
"""

from dataclasses import asdict, dataclass, field, replace
from itertools import combinations

from app.services.catalogue import get_catalogue
from app.services.eligibility import BusinessProfile, eligible, validate_bundle
from app.services.pricing import price_bundle, quantity_for

PRIMARY = ("P01", "P02", "P03", "P04", "P05", "P06")
# Nearest substitute when a product becomes ineligible (best first).
SWAP = {
    "P03": ("P02", "P01", "P04"),
    "P02": ("P01", "P04"),
    "P01": ("P04",),
    "P05": ("P03", "P02", "P01"),
    "P06": ("P05", "P03", "P02"),
    "P10": ("P09",),
    "P12": ("P08", "P07"),
    "P13": ("P08", "P07"),
    "P15": ("P18",),
    "P14": ("P18",),
    "P21": ("P20",),
    "P08": ("P07",),
    "P24": ("P25",),
}
# Cheaper version of the same thing, used to fit a budget.
DOWNGRADE = {"P03": "P02", "P02": "P01", "P06": "P05", "P08": "P07", "P10": "P09", "P17": None}
MAX_MOVES = 3


@dataclass
class Change:
    kind: str  # add / remove / swap / qty / profile
    product: str
    detail: str
    rule: str | None = None
    to: str | None = None


@dataclass
class Option:
    id: str
    kind: str  # repaired / within_budget / keep_must_haves / fit_budget / handoff
    label: str
    items: dict[str, int]
    monthly_total: int
    setup_total: int
    contract_months: int
    eta_days: int
    fits_budget: bool
    changes: list[Change] = field(default_factory=list)
    unmet: list[str] = field(default_factory=list)  # must-haves / needs this option drops


@dataclass
class RepairResult:
    problems: list[dict]
    options: list[Option]
    recommended: str | None
    needs_choice: bool
    summary: str

    def as_dict(self) -> dict:
        d = asdict(self)
        names = get_catalogue()
        d["names"] = {pid: p.name for pid, p in names.items()}
        for o in d["options"]:
            o["lines"] = [
                {"product_id": pid, "name": names[pid].name, "qty": qty} for pid, qty in o["items"].items()
            ]
        return d


@dataclass(frozen=True)
class ChangeRequest:
    budget: int | None = None
    must_have: frozenset[str] = frozenset()
    add: frozenset[str] = frozenset()
    remove: frozenset[str] = frozenset()
    sites: int | None = None
    city_tier: int | None = None
    employees: int | None = None
    gstin_active: bool | None = None
    connection: str | None = None  # owner insists on this primary connection


def _name(pid: str) -> str:
    return get_catalogue()[pid].name


def _inr(n: int) -> str:
    return f"₹{n:,}"


def _valid(items: dict[str, int], biz: BusinessProfile) -> bool:
    catalogue = get_catalogue()
    return all(eligible(catalogue[p], biz).ok for p in items) and validate_bundle(items.keys()).ok


def _price(items: dict[str, int], biz: BusinessProfile, addons: frozenset[str]):
    return price_bundle(items, biz, "custom", addons)


def _make(oid, kind, label, items, biz, budget, changes, unmet, addons) -> Option:
    priced = _price(items, biz, addons)
    return Option(
        id=oid,
        kind=kind,
        label=label,
        items=dict(items),
        monthly_total=priced.monthly_total,
        setup_total=priced.setup_total,
        contract_months=priced.contract_months,
        eta_days=priced.eta_days,
        fits_budget=budget is None or priced.monthly_total <= budget,
        changes=list(changes),
        unmet=list(unmet),
    )


def _repair_rules(
    items: dict[str, int], biz: BusinessProfile, forced: str | None, protect: set[str]
) -> tuple[dict[str, int], list[Change], list[str], list[dict], list[str]]:
    """Eligibility then dependencies. Returns items, changes, unmet, problems, handoff needs."""
    catalogue = get_catalogue()
    out = dict(items)
    changes: list[Change] = []
    unmet: list[str] = []
    problems: list[dict] = []
    handoff: list[str] = []

    # 1. eligibility
    for pid in list(out):
        e = eligible(catalogue[pid], biz)
        if e.ok:
            continue
        problems.append({"rule": e.rules[0], "product": pid, "message": e.reasons[0]})
        if pid == forced:
            handoff.append(f"{_name(pid)} isn't available here: {e.reasons[0]}")
            out.pop(pid)
            continue
        alt = next((a for a in SWAP.get(pid, ()) if a not in out and eligible(catalogue[a], biz).ok), None)
        out.pop(pid)
        if alt in PRIMARY and any(p in PRIMARY for p in out):
            alt = None  # already has a working connection; never stack a second one
        if alt and not (alt in PRIMARY and forced):
            out[alt] = quantity_for(catalogue[alt], biz)
            changes.append(
                Change("swap", pid, f"{e.reasons[0]}; nearest option is {_name(alt)}", e.rules[0], alt)
            )
        else:
            changes.append(Change("remove", pid, e.reasons[0], e.rules[0]))
            if pid in protect:
                unmet.append(pid)

    # 2. dependencies: every add-on that needs a base connection must have one
    for _ in range(3):
        check = validate_bundle(out.keys())
        if check.ok:
            break
        for v in check.violations:
            if v.product_id not in out:
                continue
            problems.append({"rule": "requires_one_of", "product": v.product_id, "message": v.message})
            current_primary = [p for p in out if p in PRIMARY]
            if forced:
                # The owner chose this connection; we don't override it. The need goes to a person.
                out.pop(v.product_id)
                changes.append(
                    Change(
                        "remove",
                        v.product_id,
                        f"{_name(v.product_id)} doesn't work with {_name(forced)}",
                        "requires_one_of",
                    )
                )
                handoff.append(
                    f"{_name(v.product_id)} needs one of: {', '.join(_name(d) for d in v.needs_one_of)}"
                )
                if v.product_id in protect:
                    unmet.append(v.product_id)
                continue
            base = next(
                (
                    d
                    for d in sorted(v.needs_one_of, key=lambda d: catalogue[d].price_min)
                    if eligible(catalogue[d], biz).ok
                ),
                None,
            )
            if base is None:
                out.pop(v.product_id)
                changes.append(
                    Change("remove", v.product_id, "no eligible connection supports it", "requires_one_of")
                )
                if v.product_id in protect:
                    unmet.append(v.product_id)
                continue
            for old in current_primary:
                if old not in v.needs_one_of and old not in protect:
                    out.pop(old)
                    changes.append(
                        Change(
                            "swap",
                            old,
                            f"{_name(v.product_id)} needs a fixed line; {_name(old)} can't carry it",
                            "requires_one_of",
                            base,
                        )
                    )
                    break
            else:
                changes.append(
                    Change("add", base, f"{_name(v.product_id)} needs a base connection", "requires_one_of")
                )
            out[base] = quantity_for(catalogue[base], biz)
    return out, changes, unmet, problems, handoff


def _budget_moves(items: dict[str, int], protect: set[str]) -> list[tuple[str, str, str | None]]:
    moves = []
    for pid in items:
        if pid in protect:
            continue
        moves.append(("remove", pid, None))
        if (down := DOWNGRADE.get(pid)) and down not in items:
            moves.append(("downgrade", pid, down))
    return moves


def _keeps_connection(before: dict[str, int], after: dict[str, int]) -> bool:
    """Budget cuts may downgrade the connection, never remove the last one:
    a plan without internet isn't a cheaper version of the same plan."""
    had = any(p in PRIMARY for p in before)
    return not had or any(p in PRIMARY for p in after)


def _apply_moves(items, moves, biz):
    catalogue = get_catalogue()
    out = dict(items)
    touched = set()
    changes = []
    for kind, pid, to in moves:
        if pid in touched or pid not in out:
            return None
        touched.add(pid)
        out.pop(pid)
        if kind == "downgrade":
            out[to] = quantity_for(catalogue[to], biz)
            changes.append(Change("swap", pid, f"switch to {_name(to)} to save money", "budget", to))
        else:
            changes.append(Change("remove", pid, "dropped to fit your budget", "budget"))
    if not out or not _keeps_connection(items, out):
        return None
    return out, changes


def _fit_budget(items, biz, budget, protect, addons):
    """Fewest moves that bring the total within budget, keeping the most value."""
    best = None
    moves = _budget_moves(items, protect)
    for n in range(1, MAX_MOVES + 1):
        for combo in combinations(moves, n):
            applied = _apply_moves(items, combo, biz)
            if applied is None:
                continue
            cand, changes = applied
            if not _valid(cand, biz):
                continue
            total = _price(cand, biz, addons).monthly_total
            if total <= budget and (best is None or total > best[0]):
                best = (total, cand, changes)
        if best:
            return best[1], best[2]
    return _greedy_fit(items, biz, budget, protect, addons)


def _greedy_fit(items, biz, budget, protect, addons):
    """Big gaps: keep dropping the costliest optional item (dependants before
    the connection they rely on) until the plan fits or nothing optional is left."""
    catalogue = get_catalogue()
    out = dict(items)
    changes: list[Change] = []
    while _price(out, biz, addons).monthly_total > budget:
        priced = {i.product_id: i.monthly for i in _price(out, biz, addons).items}
        candidates = sorted((p for p in out if p not in protect), key=lambda p: -priced[p])
        for pid in candidates:
            trial = {k: v for k, v in out.items() if k != pid}
            if trial and _keeps_connection(out, trial) and _valid(trial, biz):
                out = trial
                changes.append(Change("remove", pid, "dropped to fit your budget", "budget"))
                break
            down = DOWNGRADE.get(pid)
            if down and down not in out:
                trial = {**trial, down: quantity_for(catalogue[down], biz)}
                if (
                    _valid(trial, biz)
                    and _price(trial, biz, addons).monthly_total < _price(out, biz, addons).monthly_total
                ):
                    out = trial
                    changes.append(
                        Change("swap", pid, f"switch to {_name(down)} to save money", "budget", down)
                    )
                    break
        else:
            return None  # nothing optional left to drop
    return (out, changes) if changes else None


def analyse(current: dict[str, int], biz: BusinessProfile, req: ChangeRequest) -> RepairResult:
    catalogue = get_catalogue()
    unknown = [
        p for p in req.add | req.remove | req.must_have | {req.connection or "P01"} if p not in catalogue
    ]
    if unknown:
        raise ValueError(f"Unknown products: {', '.join(sorted(unknown))}")

    # What changed about the business
    profile_changes: list[Change] = []
    new_biz = biz
    for attr, value, label in (
        ("sites", req.sites, "sites"),
        ("city_tier", req.city_tier, "city tier"),
        ("employees", req.employees, "employees"),
        ("gstin_active", req.gstin_active, "active GST registration"),
    ):
        if value is not None and getattr(biz, attr) != value:
            new_biz = replace(new_biz, **{attr: value})
            profile_changes.append(Change("profile", attr, f"{label}: {getattr(biz, attr)} → {value}"))

    wanted = dict(current)
    owner_changes: list[Change] = []
    for pid in req.remove:
        if wanted.pop(pid, None) is not None:
            owner_changes.append(Change("remove", pid, "you removed it"))
    for pid in req.add:
        if pid in PRIMARY and pid not in wanted:
            # A new connection replaces the current one rather than stacking on it.
            for old in [p for p in wanted if p in PRIMARY]:
                wanted.pop(old)
                owner_changes.append(Change("swap", old, f"you chose {_name(pid)}", None, pid))
            wanted[pid] = quantity_for(catalogue[pid], new_biz)
        elif pid not in wanted:
            wanted[pid] = quantity_for(catalogue[pid], new_biz)
            owner_changes.append(Change("add", pid, "you asked for it"))
    if req.connection:
        for old in [p for p in wanted if p in PRIMARY and p != req.connection]:
            wanted.pop(old)
            owner_changes.append(
                Change("swap", old, f"you chose {_name(req.connection)}", None, req.connection)
            )
        wanted[req.connection] = quantity_for(catalogue[req.connection], new_biz)

    protect = set(req.must_have) | set(req.add)
    addons = frozenset(req.add)
    repaired, changes, unmet, problems, handoff = _repair_rules(wanted, new_biz, req.connection, protect)
    for pid in list(repaired):  # quantities follow the (possibly changed) business size
        q = quantity_for(catalogue[pid], new_biz)
        if pid in current and current[pid] != q and pid in wanted:
            changes.append(Change("qty", pid, f"{current[pid]} → {q} for {new_biz.sites} site(s)"))
        repaired[pid] = q

    base_changes = profile_changes + owner_changes + changes
    options: list[Option] = []
    if repaired and _valid(repaired, new_biz):
        base = _make(
            "as_asked",
            "repaired",
            "Your changes, made valid",
            repaired,
            new_biz,
            req.budget,
            base_changes,
            unmet,
            addons,
        )
        options.append(base)
        if req.budget is not None and not base.fits_budget:
            gap = base.monthly_total - req.budget
            problems.append(
                {
                    "rule": "budget",
                    "product": None,
                    "message": f"This comes to {_inr(base.monthly_total)} a month, {_inr(gap)} over your {_inr(req.budget)} budget",
                }
            )
            fit = _fit_budget(repaired, new_biz, req.budget, protect, addons)
            if fit:
                items, moves = fit
                options.append(
                    _make("within_budget", "within_budget", "Smallest change that fits your budget", items, new_biz,
                          req.budget, base_changes + moves, unmet, addons)
                )  # fmt: skip
            else:
                # Trade-off: nothing keeps every must-have within budget.
                base.kind, base.label = "keep_must_haves", "Keep everything you marked essential"
                relaxed = _fit_budget(repaired, new_biz, req.budget, set(), addons)
                if relaxed:
                    items, moves = relaxed
                    dropped = [m.product for m in moves if m.product in protect]
                    options.append(
                        _make("fit_budget", "fit_budget", "Stay within budget, drop an essential", items, new_biz,
                              req.budget, base_changes + moves, unmet + dropped, addons)
                    )  # fmt: skip

    if handoff or unmet:
        keep = [
            _name(p) for p in sorted(set(unmet) | {c.product for c in changes if c.rule == "requires_one_of"})
        ]
        options.append(
            Option(
                id="handoff",
                kind="handoff",
                label="Ask a specialist to assess the site",
                items={},
                monthly_total=0,
                setup_total=0,
                contract_months=0,
                eta_days=0,
                fits_budget=True,
                changes=[Change("profile", "handoff", "; ".join(handoff) or "needs a person to plan")],
                unmet=sorted(set(unmet)),
            )
        )
        if keep:
            options[-1].changes.append(
                Change("profile", "keep", "We'll keep these needs on file: " + ", ".join(keep))
            )

    # The chosen connection can't carry a need: also offer keeping the original
    # connection, so the need still works without a site visit.
    if req.connection and handoff:
        alt = analyse(current, biz, replace(req, connection=None))
        keep = next((o for o in alt.options if o.kind != "handoff" and not o.unmet), None)
        if keep:
            keep.id, keep.kind = "keep_connection", "alternative"
            keep.label = "Keep your current connection so everything works"
            options.insert(1, keep)

    # Every returned option is checked again by the rules engine, and none may
    # leave a business that had internet without a connection (e.g. the chosen
    # connection isn't available: keeping the current one or a specialist covers it).
    options = [
        o
        for o in options
        if o.kind == "handoff" or (_valid(o.items, new_biz) and _keeps_connection(current, o.items))
    ]

    fitting = [o for o in options if o.kind != "handoff" and o.fits_budget and not o.unmet]
    recommended = min(fitting, key=lambda o: len(o.changes)).id if fitting else None
    needs_choice = recommended is None and len([o for o in options if o.kind != "handoff"]) > 0
    summary = _summary(options, recommended, problems, req.budget)
    return RepairResult(problems, options, recommended, needs_choice, summary)


def _summary(options: list[Option], recommended: str | None, problems: list[dict], budget: int | None) -> str:
    if not problems:
        return "Nothing breaks: your plan still works with these changes."
    rec = next((o for o in options if o.id == recommended), None)
    if rec:
        n = len([c for c in rec.changes if c.rule is not None])  # changes we made, not the owner's
        return f"{problems[0]['message']}. Smallest fix: {n} change(s), {_inr(rec.monthly_total)} a month."
    if any(o.kind == "fit_budget" for o in options):
        return f"{problems[-1]['message']}. You can keep every essential, or stay within budget by dropping one. Your call."
    if any(o.kind == "handoff" for o in options):
        return f"{problems[0]['message']}. A specialist can assess the site and keep your needs on file."
    return problems[0]["message"]
