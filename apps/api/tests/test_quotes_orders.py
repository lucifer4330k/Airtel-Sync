from app.services.registry import gstin_registry

ACTIVE_GSTIN = next(g for g, r in gstin_registry().items() if r["status"] == "Active")
CLINIC = {"segment": "prof", "city_tier": 1, "employees": 12, "sites": 1, "gstin": ACTIVE_GSTIN}


def make_quotes(client, profile=CLINIC):
    r = client.post("/api/v1/quotes", json={"profile": profile})
    assert r.status_code == 201, r.text
    body = r.json()
    return body, {"X-Owner-Token": body["owner_token"]}


def test_create_quotes_persists_three_tiers(client):
    body, _ = make_quotes(client)
    tiers = [q["tier"] for q in body["quotes"]]
    assert tiers == ["good", "better", "best"]
    assert body["recommended"] == body["quotes"][1]["id"]
    for q in body["quotes"]:
        assert q["monthly_total"] == sum(i["monthly"] for i in q["items"])
        assert q["addons"], "owner view lists add-on options"


def test_toggle_addon_reprices_and_validates(client):
    body, h = make_quotes(client)
    q = body["quotes"][0]
    option = next(o for o in q["addons"] if not o["included"] and o["available"])
    r = client.patch(
        f"/api/v1/quotes/{q['id']}/items",
        json={"product_id": option["product_id"], "include": True},
        headers=h,
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["monthly_total"] > q["monthly_total"]
    added = next(i for i in after["items"] if i["product_id"] == option["product_id"])
    assert added["is_addon"]

    r = client.patch(
        f"/api/v1/quotes/{q['id']}/items",
        json={"product_id": option["product_id"], "include": False},
        headers=h,
    )
    assert r.json()["monthly_total"] == q["monthly_total"]


def test_cannot_remove_connection_that_others_need(client):
    body, h = make_quotes(client, {"segment": "multi", "city_tier": 1, "employees": 30, "sites": 4})
    q = body["quotes"][1]  # better: fibre + failover + CCTV ...
    fibre = next(i["product_id"] for i in q["items"] if i["product_id"] in {"P01", "P02", "P03"})
    r = client.patch(
        f"/api/v1/quotes/{q['id']}/items", json={"product_id": fibre, "include": False}, headers=h
    )
    assert r.status_code == 422
    assert "needs this connection" in r.json()["detail"]


def test_ineligible_addon_is_blocked_with_reason(client):
    body, h = make_quotes(client, {"segment": "micro", "city_tier": 2, "employees": 3, "sites": 1})
    q = body["quotes"][0]
    whatsapp = next(o for o in q["addons"] if o["product_id"] == "P15")
    assert not whatsapp["available"] and "GST" in whatsapp["reason"]
    r = client.patch(
        f"/api/v1/quotes/{q['id']}/items", json={"product_id": "P15", "include": True}, headers=h
    )
    assert r.status_code == 422


def test_share_link_is_read_only(client):
    body, h = make_quotes(client)
    q = body["quotes"][0]
    assert client.get(f"/api/v1/quotes/{q['id']}").status_code == 404
    shared = client.get(f"/api/v1/quotes/{q['id']}", params={"share": q["share_token"]})
    assert shared.status_code == 200 and shared.json()["addons"] == []
    r = client.patch(
        f"/api/v1/quotes/{q['id']}/items",
        json={"product_id": "P17", "include": True},
        headers={"X-Owner-Token": q["share_token"]},
    )
    assert r.status_code == 404


def test_checkout_creates_order_and_notification(client):
    body, h = make_quotes(client)
    q = body["quotes"][1]
    r = client.post(f"/api/v1/quotes/{q['id']}/accept", json={"phone": "9876543210"}, headers=h)
    assert r.status_code == 201, r.text
    order_id = r.json()["order_id"]
    assert r.json()["payment_ref"].startswith("mdt_test_")

    # quote is locked, siblings superseded
    assert (
        client.post(f"/api/v1/quotes/{q['id']}/accept", json={"phone": "9876543210"}, headers=h).status_code
        == 409
    )
    sibling = client.get(f"/api/v1/quotes/{body['quotes'][0]['id']}", headers=h).json()
    assert sibling["status"] == "superseded"

    order = client.get(f"/api/v1/orders/{order_id}", headers=h).json()
    assert order["state"] == "order_placed"
    assert order["steps"][0]["done"] and not order["steps"][1]["done"]
    assert order["slot_options"]
    assert [e["event"] for e in order["events"]] == ["order_placed"]

    slot = order["slot_options"][3]["start"]
    r = client.post(f"/api/v1/orders/{order_id}/reschedule", json={"start": slot}, headers=h)
    assert r.status_code == 200 and r.json()["events"][-1]["event"] == "rescheduled"
    assert (
        client.post(
            f"/api/v1/orders/{order_id}/reschedule", json={"start": "2030-01-01T10:00"}, headers=h
        ).status_code
        == 422
    )


def test_bad_phone_rejected(client):
    body, h = make_quotes(client)
    q = body["quotes"][0]
    assert (
        client.post(f"/api/v1/quotes/{q['id']}/accept", json={"phone": "12345"}, headers=h).status_code == 422
    )


def test_kyc_consent_attaches_to_checkout_business(client):
    body, h = make_quotes(client)
    r = client.post("/api/v1/kyc/consent", json={"kyc": True, "business_id": body["business_id"]}, headers=h)
    assert r.status_code == 201 and r.json()["business_id"] == body["business_id"]
    forged = client.post("/api/v1/kyc/consent", json={"kyc": True, "business_id": body["business_id"]})
    assert forged.status_code == 404
