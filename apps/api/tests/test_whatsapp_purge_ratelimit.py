from datetime import date, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import KycDocument

KDOCS = get_settings().data_dir / "kyc_documents"


def wa(text, sender="919876543210"):
    message = {"from": sender, "type": "text", "text": {"body": text}}
    return {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}


def test_webhook_verification(client):
    params = {"hub.mode": "subscribe", "hub.verify_token": "udyam-dev-verify", "hub.challenge": "42"}
    ok = client.get("/api/v1/whatsapp/webhook", params=params)
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get("/api/v1/whatsapp/webhook", params={**params, "hub.verify_token": "x"})
    assert bad.status_code == 403


def test_whatsapp_conversation_reaches_a_plan_link(client):
    first = client.post(
        "/api/v1/whatsapp/webhook", json=wa("Kirana shop in Indore, 3 people, no GST, need UPI billing")
    )
    reply = first.json()["replies"][0]
    assert reply["to"] == "XXXXXX3210"
    last = reply["text"]
    for _ in range(4):
        if "/resume?" in last:
            break
        last = client.post("/api/v1/whatsapp/webhook", json=wa("nothing else")).json()["replies"][0]["text"]
    assert "/resume?b=" in last and "Cloud POS & Billing" in last
    other = client.post("/api/v1/whatsapp/webhook", json=wa("hello", sender="919999911111")).json()
    assert "business" in other["replies"][0]["text"].lower()


def test_purge_removes_images_but_keeps_results(client):
    from app.db import get_db
    from app.main import app
    from app.workers.purge_documents import purge

    profile = {"segment": "micro", "city_tier": 2, "employees": 2, "sites": 1}
    r = client.post("/api/v1/kyc/consent", json={"kyc": True, "profile": profile}).json()
    client.post(
        "/api/v1/kyc/documents",
        data={"business_id": str(r["business_id"]), "doc_type": "address_proof"},
        files={"file": ("x.png", (KDOCS / "K03_address_proof.png").read_bytes(), "image/png")},
        headers={"X-Owner-Token": r["token"]},
    )
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        assert purge(db, today=date.today()) == 0
        assert purge(db, today=date.today() + timedelta(days=31)) == 1
        doc = db.scalars(select(KycDocument).where(KycDocument.business_id == r["business_id"])).one()
        assert doc.storage_key is None and doc.extracted.get("analysis")
    finally:
        gen.close()


def test_rate_limit(client, monkeypatch):
    from app.core import ratelimit

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    ratelimit.reset()
    body = {"username": "x", "password": "y"}
    codes = [client.post("/api/v1/console/login", json=body).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[-1] == 429
    ratelimit.reset()
