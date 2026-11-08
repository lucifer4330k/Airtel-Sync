"""Runs every persona in advisor_scenarios/*.yaml against the real API."""

from pathlib import Path

import pytest
import yaml

from app.services.catalogue import get_catalogue
from app.services.eligibility import eligible, validate_bundle
from app.services.quotes import profile_of
from app.services.registry import gstin_registry

REG = gstin_registry()
SUBS = {
    "{ACTIVE_GSTIN}": next(g for g, r in REG.items() if r["status"] == "Active"),
    "{CANCELLED_GSTIN}": next(g for g, r in REG.items() if r["status"] == "Cancelled"),
}
PERSONAS = [
    p
    for f in sorted(Path(__file__).parent.glob("advisor_scenarios/*.yaml"))
    for p in yaml.safe_load(f.read_text("utf-8"))
]


def sub(text: str) -> str:
    for k, v in SUBS.items():
        text = text.replace(k, v)
    return text


def run(client, persona) -> tuple[list[dict], dict | None]:
    start = client.post("/api/v1/advisor/sessions", json={"channel": "web"}).json()
    h = {"X-Session-Token": start["token"]}
    sid = start["session_id"]
    turns = [
        client.post(
            f"/api/v1/advisor/sessions/{sid}/messages", json={"text": sub(persona["open"])}, headers=h
        ).json()
    ]
    answers = persona.get("answers", {})
    for _ in range(10):
        last = turns[-1]
        if last.get("done") or last.get("needs_human"):
            break
        from app.db import get_db  # noqa: F401  (session state lives in the DB)

        awaiting = _awaiting(client, sid)
        text = answers.get(awaiting)
        if text is None:
            pytest.fail(
                f"{persona['id']}: advisor asked '{awaiting}' with no scripted answer. Reply: {last['reply']}"
            )
        turns.append(
            client.post(
                f"/api/v1/advisor/sessions/{sid}/messages", json={"text": sub(text)}, headers=h
            ).json()
        )
    card = next((t["bundle"] for t in reversed(turns) if t.get("bundle")), None)
    return turns, card


def _awaiting(client, sid) -> str | None:
    from app.db import get_db
    from app.main import app
    from app.models import AdvisorSession

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        return (db.get(AdvisorSession, sid).slots or {}).get("awaiting")
    finally:
        gen.close()


@pytest.mark.parametrize("persona", PERSONAS, ids=[p["id"] for p in PERSONAS])
def test_persona(client, persona):
    turns, card = run(client, persona)
    replies = "\n".join(t["reply"] for t in turns)
    assert len(turns) <= 7, f"too many turns ({len(turns)})"

    if persona.get("needs_human") is not None:
        flagged = any(t.get("needs_human") for t in turns) or _lead_flag(client, card)
        assert flagged == persona["needs_human"], replies
    if "note" in persona:
        assert persona["note"] in replies, replies
    if not card:
        assert not persona.get("include"), f"no plan produced:\n{replies}"
        return

    h = {"X-Owner-Token": card["owner_token"]}
    quotes = [client.get(f"/api/v1/quotes/{q['id']}", headers=h).json() for q in card["quotes"]]
    rec = next(q for q in quotes if q["id"] == card["recommended_quote_id"])
    rec_ids = {i["product_id"] for i in rec["items"]}
    for pid in persona.get("include", []):
        assert pid in rec_ids, f"{pid} missing from recommended plan {sorted(rec_ids)}\n{replies}"

    biz = _business(card["business_id"])
    if "segment" in persona:
        assert biz.segment == persona["segment"]
    profile = profile_of(biz)
    catalogue = get_catalogue()
    for q in quotes:
        ids = [i["product_id"] for i in q["items"]]
        bad = [p for p in ids if not eligible(catalogue[p], profile).ok]
        assert not bad, f"{q['tier']} holds ineligible {bad}"
        assert validate_bundle(ids).ok
        for pid in persona.get("never", []):
            assert pid not in ids, f"{pid} must never appear ({q['tier']}: {ids})"


def _business(business_id):
    from app.db import get_db
    from app.main import app
    from app.models import Business

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        return db.get(Business, business_id)
    finally:
        gen.close()


def _lead_flag(client, card) -> bool:
    if not card:
        return False
    from sqlalchemy import select

    from app.db import get_db
    from app.main import app
    from app.models import Lead

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        lead = db.scalar(select(Lead).where(Lead.business_id == card["business_id"]))
        return bool(lead and lead.needs_human)
    finally:
        gen.close()
