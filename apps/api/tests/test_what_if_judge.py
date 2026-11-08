from sqlalchemy import select

from app.models import Lead


def clinic_quote(client):
    r = client.post(
        "/api/v1/quotes",
        json={"profile": {"segment": "prof", "city_tier": 1, "employees": 5, "sites": 1}},
    ).json()
    return r["quotes"][0], {"X-Owner-Token": r["owner_token"]}, r["business_id"]


def test_what_if_explains_and_changes_nothing(client):
    q, h, _ = clinic_quote(client)
    r = client.post(f"/api/v1/quotes/{q['id']}/what-if", json={"budget": 500, "add": ["P09"]}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["problems"] and body["problems"][-1]["rule"] == "budget"
    assert body["summary"]
    assert all("lines" in o for o in body["options"])
    # nothing persisted
    after = client.get(f"/api/v1/quotes/{q['id']}", headers=h).json()
    assert after["monthly_total"] == q["monthly_total"]


def test_apply_repair_updates_quote(client):
    q, h, _ = clinic_quote(client)
    wi = client.post(f"/api/v1/quotes/{q['id']}/what-if", json={"add": ["P09"]}, headers=h).json()
    rec = wi["recommended"]
    r = client.post(
        f"/api/v1/quotes/{q['id']}/what-if/apply", json={"add": ["P09"], "option_id": rec}, headers=h
    )
    assert r.status_code == 200, r.text
    assert "P09" in {i["product_id"] for i in r.json()["items"]}


def test_apply_handoff_flags_lead_with_needs(client):
    q, h, bid = clinic_quote(client)
    body = {"add": ["P09"], "connection": "P04", "must_have": ["P09"]}
    wi = client.post(f"/api/v1/quotes/{q['id']}/what-if", json=body, headers=h).json()
    assert any(o["kind"] == "handoff" for o in wi["options"])
    r = client.post(
        f"/api/v1/quotes/{q['id']}/what-if/apply", json={**body, "option_id": "handoff"}, headers=h
    )
    assert r.json()["handoff"] is True

    from app.db import get_db
    from app.main import app

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        lead = db.scalar(select(Lead).where(Lead.business_id == bid))
        assert lead.needs_human and "Backup 4G/5G Failover" in lead.needs_human_reason
    finally:
        gen.close()


def test_what_if_requires_owner_and_rejects_gaining_gst(client):
    q, h, _ = clinic_quote(client)
    assert client.post(f"/api/v1/quotes/{q['id']}/what-if", json={}).status_code == 404
    bad = client.post(f"/api/v1/quotes/{q['id']}/what-if", json={"gstin_active": True}, headers=h)
    assert bad.status_code == 422


def test_judge_challenge_shows_rule_and_clean_audit(client):
    scenarios = client.get("/api/v1/judge/scenarios").json()
    clinic = next(s for s in scenarios if s["id"] == "clinic")["profile"]
    plan = client.post("/api/v1/judge/plan", json=clinic).json()
    items = {i["product_id"]: i["qty"] for i in plan["tiers"][0]["items"]}
    assert any(not r["eligible"] for r in plan["rules"])  # e.g. leased line needs 10 staff

    r = client.post(
        "/api/v1/judge/challenge",
        json={"profile": clinic, "items": items, "change": {"city_tier": 2, "add": ["P03"]}},
    ).json()
    assert any(p["rule"] == "city_tier" for p in r["problems"])
    assert all(a["ineligible"] == [] and a["dependencies_ok"] for a in r["audit"])


def test_scorecard_endpoint(client):
    r = client.get("/api/v1/judge/scorecard")
    assert r.status_code == 200 and "available" in r.json()
