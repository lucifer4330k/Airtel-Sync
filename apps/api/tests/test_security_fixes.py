import hashlib
import hmac
import json

from app.core.config import get_settings


def wa(text, sender="919876543210"):
    message = {"from": sender, "type": "text", "text": {"body": text}}
    return {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}


def login(client, username):
    r = client.post("/api/v1/console/login", json={"username": username, "password": f"pw-{username}"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def place_order(client, city_gstin=None):
    q = client.post(
        "/api/v1/quotes", json={"profile": {"segment": "micro", "city_tier": 2, "employees": 3, "sites": 1}}
    ).json()
    h = {"X-Owner-Token": q["owner_token"]}
    order_id = client.post(
        f"/api/v1/quotes/{q['quotes'][0]['id']}/accept", json={"phone": "9876543210"}, headers=h
    ).json()["order_id"]
    return order_id, q["owner_token"]


def test_outbox_never_exposes_owner_tokens(client):
    order_id, token = place_order(client)
    admin = login(client, "admin")
    bodies = [n["body"] for n in client.get("/api/v1/console/notifications", headers=admin).json()]
    assert bodies and all(token not in b for b in bodies)
    assert any("?t=[redacted]" in b for b in bodies)


def test_outbox_is_scoped_for_reps(client):
    order_id, _ = place_order(client)  # business has no city -> outside the Pune rep's territory
    rep = login(client, "rep.pune")
    assert client.get("/api/v1/console/notifications", headers=rep).json() == []
    assert (
        client.get("/api/v1/console/notifications", params={"order_id": order_id}, headers=rep).json() == []
    )


def test_webhook_fails_closed_without_secret(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_allow_unsigned", False)
    r = client.post("/api/v1/whatsapp/webhook", json=wa("hello"))
    assert r.status_code == 503


def test_signed_webhook_works_and_does_not_echo(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_allow_unsigned", False)
    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "app-secret")
    body = json.dumps(wa("Kirana in Indore, 3 people, no GST")).encode()
    sig = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    bad = client.post("/api/v1/whatsapp/webhook", content=body, headers={"x-hub-signature-256": "sha256=00"})
    assert bad.status_code == 401
    ok = client.post(
        "/api/v1/whatsapp/webhook",
        content=body,
        headers={"x-hub-signature-256": sig, "content-type": "application/json"},
    )
    assert ok.status_code == 200 and ok.json() == {"ok": True}
