from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuditLog, Lead

KDOCS = get_settings().data_dir / "kyc_documents"
TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]


def login(client, username):
    r = client.post("/api/v1/console/login", json={"username": username, "password": f"pw-{username}"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def db_session():
    from app.db import get_db
    from app.main import app

    gen = app.dependency_overrides[get_db]()
    return gen, next(gen)


def make_lead(client, city="Pune", text="Dental clinic in {city}, 8 staff, no gst, please call me"):
    s = client.post("/api/v1/advisor/sessions", json={}).json()
    h = {"X-Session-Token": s["token"]}
    client.post(
        f"/api/v1/advisor/sessions/{s['session_id']}/messages",
        json={"text": text.format(city=city)},
        headers=h,
    )
    gen, db = db_session()
    try:
        return db.scalars(select(Lead).order_by(Lead.id.desc())).first().id
    finally:
        gen.close()


def test_login_rejects_bad_password(client):
    assert (
        client.post("/api/v1/console/login", json={"username": "admin", "password": "nope"}).status_code
        == 401
    )
    assert client.get("/api/v1/console/leads").status_code == 401
    assert client.get("/api/v1/console/leads", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_needs_human_lead_is_scored_and_scoped(client):
    pune_lead = make_lead(client, "Pune")
    mumbai_lead = make_lead(client, "Mumbai")
    admin = login(client, "admin")
    rep = login(client, "rep.pune")

    items = client.get("/api/v1/console/leads", params={"view": "needs_human"}, headers=admin).json()["items"]
    row = next(i for i in items if i["id"] == pune_lead)
    assert row["needs_human"] and "call" in row["needs_human_reason"].lower()
    assert 0 < row["score"] < 1 and len(row["reasons"]) == 3

    rep_ids = {
        i["id"]
        for i in client.get("/api/v1/console/leads", params={"view": "all"}, headers=rep).json()["items"]
    }
    assert pune_lead in rep_ids and mumbai_lead not in rep_ids
    assert client.get(f"/api/v1/console/leads/{mumbai_lead}", headers=rep).status_code == 404


def test_detail_is_audited_and_masked(client):
    lead_id = make_lead(client, "Pune", "Clinic in {city}, 8 staff, no gst, call me on 9876543210")
    admin = login(client, "admin")
    detail = client.get(f"/api/v1/console/leads/{lead_id}", headers=admin).json()
    assert detail["phone"] == "XXXXXX3210"
    assert all("9876543210" not in m["text"] for m in detail["transcript"])
    gen, db = db_session()
    try:
        assert db.scalar(
            select(AuditLog).where(
                AuditLog.event == "console.view_lead", AuditLog.target == f"lead:{lead_id}"
            )
        )
    finally:
        gen.close()


def test_assign_respects_territory(client):
    lead_id = make_lead(client, "Pune")
    admin = login(client, "admin")
    bad = client.post(
        f"/api/v1/console/leads/{lead_id}/assign", json={"username": "partner.mumbai"}, headers=admin
    )
    assert bad.status_code == 422 and "Mumbai" in bad.json()["detail"]
    ok = client.post(f"/api/v1/console/leads/{lead_id}/assign", json={"username": "rep.pune"}, headers=admin)
    assert ok.json()["assigned_to"] == "rep.pune"
    rep = login(client, "rep.pune")
    r = client.post(
        f"/api/v1/console/leads/{lead_id}/follow-ups",
        json={"note": "Called, visit Monday", "outcome": "visit_booked"},
        headers=rep,
    )
    assert r.status_code == 200


def test_funnel_has_history_and_live(client):
    body = client.get("/api/v1/console/funnel", headers=login(client, "admin")).json()
    stages = {s["stage"]: s["count"] for s in body["history"]["stages"]}
    assert stages["Lead"] == 5000 and stages["Activated"] == 368
    assert body["history"]["avg_days_to_activate"] == 17.6
    assert 14000 <= body["history"]["cac"] <= 16000


def test_order_actions_are_admin_only(client):
    q = client.post(
        "/api/v1/quotes", json={"profile": {"segment": "prof", "city_tier": 1, "employees": 9, "sites": 1}}
    ).json()
    h = {"X-Owner-Token": q["owner_token"]}
    order_id = client.post(
        f"/api/v1/quotes/{q['quotes'][0]['id']}/accept", json={"phone": "9876543210"}, headers=h
    ).json()["order_id"]
    rep, admin = login(client, "rep.pune"), login(client, "admin")
    assert client.post(f"/api/v1/console/orders/{order_id}/advance", headers=rep).status_code == 403
    assert (
        client.post(f"/api/v1/console/orders/{order_id}/advance", headers=admin).json()["state"]
        == "kyc_verified"
    )
    held = client.post(
        f"/api/v1/console/orders/{order_id}/hold", json={"reason": "Site access"}, headers=admin
    ).json()
    assert held["state"] == "on_hold"
    outbox = client.get("/api/v1/console/notifications", params={"order_id": order_id}, headers=admin).json()
    assert len(outbox) == 3


def test_reviewer_can_clear_a_review_check(client):
    # K10: everything passes except the signatory, which needs a reviewer.
    gstin, udyam = "27QHJXK0658U1ZL", "UDYAM-MH-00-7183141"
    q = client.post(
        "/api/v1/quotes",
        json={"profile": {"segment": "multi", "city_tier": 1, "employees": 20, "sites": 3, "gstin": gstin}},
    ).json()
    h = {"X-Owner-Token": q["owner_token"]}
    bid = q["business_id"]
    client.post("/api/v1/kyc/consent", json={"kyc": True, "business_id": bid}, headers=h)
    client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": gstin, "udyam_number": udyam}, headers=h)
    for t in TYPES:
        client.post(
            "/api/v1/kyc/documents",
            data={"business_id": str(bid), "doc_type": t},
            files={"file": ("x.png", (KDOCS / f"K10_{t}.png").read_bytes(), "image/png")},
            headers=h,
        )
    assert client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()["overall"] == "review"

    admin = login(client, "admin")
    item = next(
        i for i in client.get("/api/v1/console/kyc/queue", headers=admin).json() if i["business_id"] == bid
    )
    assert item["check"] == "signatory_match"
    r = client.post(
        f"/api/v1/console/kyc/checks/{item['check_id']}/resolve",
        json={"result": "pass", "note": "Board resolution seen"},
        headers=admin,
    )
    assert r.json()["overall"] == "pass"
    assert client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()["overall"] == "pass"
