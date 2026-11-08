from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.registry import gstin_registry, udyam_registry

DATA = get_settings().data_dir
PNG = (DATA / "kyc_documents" / "K01_gst_certificate.png").read_bytes()
PROFILE = {"segment": "prof", "city_tier": 1, "employees": 12, "sites": 1}
ALL_DOCS = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]


def storage_files() -> list[Path]:
    return [p for p in Path(get_settings().storage_dir).rglob("*") if p.is_file()]


@pytest.fixture(scope="module")
def linked_ids(leads):
    """(gstin, udyam) of an Active, proprietorship lead that has both."""
    reg = gstin_registry()
    for r in leads:
        g, u = r["gstin"], r["udyam_number"]
        if g and u and reg[g]["status"] == "Active" and "(Prop." in reg[g]["legal_name"]:
            return g, u
    raise AssertionError("no linked lead found")


def open_case(client, **extra):
    r = client.post("/api/v1/kyc/consent", json={"kyc": True, "profile": PROFILE, **extra})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["business_id"], {"X-KYC-Token": body["token"]}


def upload(client, bid, headers, doc_type, data=PNG, name="doc.png"):
    return client.post(
        "/api/v1/kyc/documents",
        data={"business_id": str(bid), "doc_type": doc_type},
        files={"file": (name, data, "image/png")},
        headers=headers,
    )


def test_kyc_consent_is_required(client):
    r = client.post("/api/v1/kyc/consent", json={"kyc": False, "profile": PROFILE})
    assert r.status_code == 422


def test_full_flow_with_proprietorship_name_match(client, linked_ids):
    gstin, udyam = linked_ids
    bid, h = open_case(client, marketing=True)

    r = client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": gstin, "udyam_number": udyam}, headers=h)
    assert r.status_code == 200
    checks = {c["name"]: c["result"] for c in r.json()["checks"]}
    # "Name (Prop. Trade)" on GST vs "Trade" on Udyam must still match.
    assert checks == {
        "gstin_format": "pass",
        "gstin_registry": "pass",
        "udyam_format": "pass",
        "udyam_registry": "pass",
        "udyam_gst_name_match": "pass",
    }

    status = client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()
    assert status["overall"] == "incomplete"
    assert status["missing"] == ALL_DOCS
    assert status["gstin"] != gstin and "XXXXX" in status["gstin"]  # masked
    assert status["consent"] == {"kyc": True, "marketing": True}


K = DATA / "kyc_documents"
K03_GSTIN, K03_UDYAM = "27XUIXG0767D1ZP", "UDYAM-MH-00-9516696"


def doc_bytes(applicant: str, doc_type: str) -> bytes:
    return (K / f"{applicant}_{doc_type}.png").read_bytes()


def test_clean_applicant_passes_and_advances_order(client):
    # Quote + checkout for a business, then KYC with K03's (clean) documents.
    q = client.post(
        "/api/v1/quotes",
        json={"profile": {"segment": "mfg", "city_tier": 2, "employees": 12, "sites": 1, "gstin": K03_GSTIN}},
    ).json()
    h = {"X-Owner-Token": q["owner_token"]}
    bid = q["business_id"]
    order_id = client.post(
        f"/api/v1/quotes/{q['quotes'][0]['id']}/accept", json={"phone": "9876543210"}, headers=h
    ).json()["order_id"]
    assert (
        client.post("/api/v1/kyc/consent", json={"kyc": True, "business_id": bid}, headers=h).status_code
        == 201
    )
    client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": K03_GSTIN, "udyam_number": K03_UDYAM}, headers=h)

    for doc in ALL_DOCS:
        r = upload(client, bid, h, doc, data=doc_bytes("K03", doc))
        assert r.status_code == 201 and r.json()["result"] == "processing"

    status = client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()
    assert status["missing"] == []
    assert status["overall"] == "pass", status["reasons"]
    assert all(d["result"] == "pass" for d in status["documents"])
    order = client.get(f"/api/v1/orders/{order_id}", headers=h).json()
    assert order["state"] == "kyc_verified"


def test_planted_problem_is_explained_and_fixable(client):
    bid, h = open_case(client)
    client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": K03_GSTIN, "udyam_number": K03_UDYAM}, headers=h)
    for doc in ["gst_certificate", "udyam_certificate", "signatory_id"]:
        upload(client, bid, h, doc, data=doc_bytes("K03", doc))
    # K11's bill is 257 days old
    upload(client, bid, h, "address_proof", data=doc_bytes("K11", "address_proof"))
    status = client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()
    assert status["overall"] == "fail"
    assert any("days old" in r for r in status["reasons"])
    # fixing it: re-upload the right bill
    upload(client, bid, h, "address_proof", data=doc_bytes("K03", "address_proof"))
    assert client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()["overall"] == "pass"


def test_wrong_document_type_is_caught(client):
    bid, h = open_case(client)
    upload(client, bid, h, "signatory_id", data=doc_bytes("K03", "address_proof"))
    doc = client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()["documents"][0]
    assert doc["result"] == "fail"
    assert any("not a signatory ID" in c["reason"] for c in doc["checks"])


def test_documents_are_encrypted_at_rest_and_view_is_audited(client):
    bid, h = open_case(client)
    before = set(storage_files())
    doc = upload(client, bid, h, "signatory_id").json()
    (stored,) = set(storage_files()) - before
    raw = stored.read_bytes()
    assert not raw.startswith(b"\x89PNG") and PNG[:64] not in raw  # ciphertext on disk

    r = client.get(f"/api/v1/kyc/{bid}/documents/{doc['id']}/file", headers=h)
    assert r.status_code == 200
    assert r.content == PNG and r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"

    _, other = open_case(client)
    assert client.get(f"/api/v1/kyc/{bid}/documents/{doc['id']}/file", headers=other).status_code == 404


def test_token_is_required_and_bound_to_case(client):
    bid, h = open_case(client)
    other, h2 = open_case(client)
    assert client.get(f"/api/v1/kyc/{bid}/status").status_code == 404
    assert client.get(f"/api/v1/kyc/{bid}/status", headers=h2).status_code == 404
    assert (
        client.get(f"/api/v1/kyc/{bid}/status", headers={"X-KYC-Token": f"{bid}.forged"}).status_code == 404
    )
    assert upload(client, bid, h2, "signatory_id").status_code == 404


def test_file_type_is_sniffed_not_trusted(client):
    bid, h = open_case(client)
    r = upload(client, bid, h, "signatory_id", data=b"<script>alert(1)</script>", name="evil.png")
    assert r.status_code == 415
    pdf = upload(client, bid, h, "signatory_id", data=b"%PDF-1.7\n...", name="id.jpg")
    assert pdf.status_code == 201
    assert pdf.json()["file"]["file_type"] == "PDF"


def test_size_limit(client):
    bid, h = open_case(client)
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    assert upload(client, bid, h, "address_proof", data=big).status_code == 413
    assert upload(client, bid, h, "address_proof", data=b"").status_code == 422


def test_reupload_replaces_old_file(client):
    bid, h = open_case(client)
    before = set(storage_files())
    upload(client, bid, h, "address_proof")
    first = set(storage_files()) - before
    upload(client, bid, h, "address_proof")
    after = set(storage_files()) - before
    assert len(first) == 1 and len(after) == 1 and first != after
    docs = client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()["documents"]
    assert [d["doc_type"] for d in docs] == ["address_proof"]


def test_cancelled_gstin_fails(client):
    cancelled = next(g for g, r in gstin_registry().items() if r["status"] == "Cancelled")
    bid, h = open_case(client)
    r = client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": cancelled}, headers=h)
    assert r.json()["result"] == "fail"
    assert "Cancelled" in r.json()["checks"][-1]["reason"]
    assert client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()["overall"] == "fail"


def test_mismatched_udyam_goes_to_review(client):
    gstin = next(g for g, r in gstin_registry().items() if r["status"] == "Active")
    gst_name = gstin_registry()[gstin]["legal_name"]
    udyam = next(u for u, r in udyam_registry().items() if r["enterprise_name"] not in gst_name)
    bid, h = open_case(client)
    r = client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": gstin, "udyam_number": udyam}, headers=h)
    match = next(c for c in r.json()["checks"] if c["name"] == "udyam_gst_name_match")
    assert match["result"] == "review"


def test_withdrawing_consent_deletes_documents(client):
    bid, h = open_case(client)
    before = set(storage_files())
    upload(client, bid, h, "signatory_id")
    assert len(set(storage_files()) - before) == 1

    r = client.post(f"/api/v1/kyc/{bid}/consent/withdraw", json={"purpose": "kyc"}, headers=h)
    assert r.json()["documents_deleted"] == 1
    assert set(storage_files()) - before == set()
    assert upload(client, bid, h, "signatory_id").status_code == 403


def test_lookup_autofill():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    gstin, rec = next(iter(gstin_registry().items()))
    body = c.get("/api/v1/kyc/lookup", params={"gstin": gstin}).json()
    assert body["record"]["legal_name"] == rec["legal_name"]
    assert c.get("/api/v1/kyc/lookup").status_code == 422
    assert c.get("/api/v1/kyc/lookup", params={"udyam": "UDYAM-XX-00-0000000"}).json()["record"] is None


def test_blank_identity_field_keeps_what_is_on_file(client):
    q = client.post(
        "/api/v1/quotes",
        json={"profile": {"segment": "mfg", "city_tier": 2, "employees": 12, "sites": 1, "gstin": K03_GSTIN}},
    ).json()
    h = {"X-Owner-Token": q["owner_token"]}
    bid = q["business_id"]
    client.post("/api/v1/kyc/consent", json={"kyc": True, "business_id": bid}, headers=h)
    client.put(f"/api/v1/kyc/{bid}/identity", json={"gstin": "", "udyam_number": K03_UDYAM}, headers=h)
    status = client.get(f"/api/v1/kyc/{bid}/status", headers=h).json()
    assert status["gstin"] and "gst_certificate" in status["required"]
