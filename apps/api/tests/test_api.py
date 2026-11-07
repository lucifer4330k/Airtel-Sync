from fastapi.testclient import TestClient

from app.main import app
from app.services.registry import gstin_registry

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["reference_date"] == "2026-07-15"


def test_mock_gstin_lookup():
    gstin, rec = next(iter(gstin_registry().items()))
    r = client.get(f"/api/v1/mock/gstin/{gstin}")
    assert r.status_code == 200
    body = r.json()
    assert body["legal_name"] == rec["legal_name"]
    assert body["status"] in {"Active", "Cancelled", "Suspended"}


def test_mock_gstin_rejects_bad_checksum():
    gstin = next(iter(gstin_registry()))
    bad = gstin[:14] + ("0" if gstin[14] != "0" else "1")
    assert client.get(f"/api/v1/mock/gstin/{bad}").status_code == 422


def test_mock_udyam_lookup():
    r = client.get("/api/v1/mock/udyam/UDYAM-KL-00-3078801")
    assert r.status_code == 200
    assert r.json()["city"] == "Kochi"
    assert client.get("/api/v1/mock/udyam/UDYAM-KL-00-0000000").status_code == 404


def test_quote_preview():
    r = client.post(
        "/api/v1/quotes/preview",
        json={"segment": "Professional offices", "city_tier": 1, "employees": 12, "sites": 1},
    )
    assert r.status_code == 200
    tiers = r.json()["tiers"]
    assert [t["tier"] for t in tiers][0] == "good"


def test_price_custom_refuses_ineligible():
    r = client.post(
        "/api/v1/quotes/price",
        json={
            "profile": {"segment": "micro", "city_tier": 2, "employees": 3, "sites": 1},
            "items": {"P03": 1, "P09": 1},
        },
    )
    assert r.status_code == 422
    reasons = r.json()["detail"]["reasons"]
    assert any("tier-1" in x for x in reasons)
