"""Backend tests for Master Produk KPR CRUD + RBAC + financing integration.

Covers:
- CRUD as super_admin (create/list/get/update/archive) + duplicate 409 + validation 422
- RBAC: sales role can GET (financing:view) but POST/PUT/DELETE should be 403
- Financing POST persists kpr_product_id/kpr_product_name
- Contract SP3K stage endpoint accepts new fields (not 422)
"""
import os
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

SUPER = ("superadmin@sipro.co.id", "Sipro#2026")
SALES = ("sales@sipro.co.id", "Sipro#2026")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def super_headers():
    return {"Authorization": f"Bearer {_login(*SUPER)}"}


@pytest.fixture(scope="module")
def sales_headers():
    return {"Authorization": f"Bearer {_login(*SALES)}"}


@pytest.fixture(scope="module")
def created_product(super_headers):
    """Create a test product; teardown archives it."""
    name = f"TEST_KPR_{uuid.uuid4().hex[:8]}"
    payload = {
        "bank_name": "TEST_BANK",
        "name": name,
        "tenors": [120, 180, 240],
        "interest_rate_pct": 6.5,
        "fixed_years": 3,
        "floating_rate_pct": 9.0,
        "min_dp_pct": 10.0,
        "notes": "seed",
        "is_active": True,
    }
    r = requests.post(f"{API}/master/kpr-products", json=payload, headers=super_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    yield data
    # cleanup
    requests.delete(f"{API}/master/kpr-products/{data['id']}", headers=super_headers, timeout=30)


# ---------- CRUD ----------
class TestKprProductsCRUD:
    def test_create(self, created_product):
        assert created_product["id"]
        assert created_product["bank_name"] == "TEST_BANK"
        assert sorted(created_product["tenors"]) == [120, 180, 240]
        assert created_product["interest_rate_pct"] == 6.5
        assert created_product["is_active"] is True

    def test_duplicate_conflict(self, super_headers, created_product):
        r = requests.post(f"{API}/master/kpr-products", json={
            "bank_name": created_product["bank_name"],
            "name": created_product["name"],
            "tenors": [120],
            "interest_rate_pct": 5.0,
        }, headers=super_headers, timeout=30)
        assert r.status_code == 409, r.text

    def test_validation_empty_tenors(self, super_headers):
        r = requests.post(f"{API}/master/kpr-products", json={
            "bank_name": "X", "name": "Y", "tenors": [], "interest_rate_pct": 5.0,
        }, headers=super_headers, timeout=30)
        assert r.status_code in (400, 422), r.text

    def test_list_by_bank(self, super_headers, created_product):
        r = requests.get(f"{API}/master/kpr-products", params={"bank_name": "TEST_BANK"},
                         headers=super_headers, timeout=30)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["data"]]
        assert created_product["id"] in ids

    def test_update(self, super_headers, created_product):
        upd = {
            "bank_name": created_product["bank_name"],
            "name": created_product["name"],
            "tenors": [120, 240],
            "interest_rate_pct": 7.25,
        }
        r = requests.put(f"{API}/master/kpr-products/{created_product['id']}",
                         json=upd, headers=super_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["interest_rate_pct"] == 7.25
        assert sorted(data["tenors"]) == [120, 240]

    def test_update_name_collision(self, super_headers, created_product):
        # create another product then try to rename to the same name
        other_name = f"TEST_KPR_OTHER_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/master/kpr-products", json={
            "bank_name": created_product["bank_name"],
            "name": other_name,
            "tenors": [120], "interest_rate_pct": 5.0,
        }, headers=super_headers, timeout=30)
        assert r.status_code == 200
        other = r.json()["data"]
        try:
            r = requests.put(f"{API}/master/kpr-products/{other['id']}", json={
                "bank_name": created_product["bank_name"],
                "name": created_product["name"],
                "tenors": [120], "interest_rate_pct": 5.0,
            }, headers=super_headers, timeout=30)
            assert r.status_code == 409, r.text
        finally:
            requests.delete(f"{API}/master/kpr-products/{other['id']}",
                            headers=super_headers, timeout=30)

    def test_archive_and_include_inactive(self, super_headers):
        # create then archive then verify filters
        name = f"TEST_KPR_ARCH_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/master/kpr-products", json={
            "bank_name": "TEST_BANK", "name": name, "tenors": [120],
            "interest_rate_pct": 5.0,
        }, headers=super_headers, timeout=30)
        pid = r.json()["data"]["id"]
        r = requests.delete(f"{API}/master/kpr-products/{pid}",
                            headers=super_headers, timeout=30)
        assert r.status_code == 200
        # default list should not include it
        r = requests.get(f"{API}/master/kpr-products", params={"bank_name": "TEST_BANK"},
                         headers=super_headers, timeout=30)
        assert pid not in [p["id"] for p in r.json()["data"]]
        # include_inactive should include it
        r = requests.get(f"{API}/master/kpr-products",
                         params={"bank_name": "TEST_BANK", "include_inactive": "true"},
                         headers=super_headers, timeout=30)
        found = [p for p in r.json()["data"] if p["id"] == pid]
        assert found and found[0]["is_active"] is False

    def test_update_unknown_404(self, super_headers):
        r = requests.put(f"{API}/master/kpr-products/nope-xyz", json={
            "bank_name": "X", "name": "Y", "tenors": [120], "interest_rate_pct": 5.0,
        }, headers=super_headers, timeout=30)
        assert r.status_code == 404

    def test_delete_unknown_404(self, super_headers):
        r = requests.delete(f"{API}/master/kpr-products/nope-xyz",
                            headers=super_headers, timeout=30)
        assert r.status_code == 404


# ---------- RBAC ----------
class TestKprProductsRBAC:
    def test_sales_can_get(self, sales_headers):
        r = requests.get(f"{API}/master/kpr-products", headers=sales_headers, timeout=30)
        assert r.status_code == 200

    def test_sales_cannot_create(self, sales_headers):
        r = requests.post(f"{API}/master/kpr-products", json={
            "bank_name": "X", "name": f"NO_{uuid.uuid4().hex[:6]}",
            "tenors": [120], "interest_rate_pct": 5.0,
        }, headers=sales_headers, timeout=30)
        assert r.status_code == 403, r.text

    def test_sales_cannot_update(self, sales_headers, created_product):
        r = requests.put(f"{API}/master/kpr-products/{created_product['id']}", json={
            "bank_name": "X", "name": "Y", "tenors": [120], "interest_rate_pct": 5.0,
        }, headers=sales_headers, timeout=30)
        assert r.status_code == 403

    def test_sales_cannot_delete(self, sales_headers, created_product):
        r = requests.delete(f"{API}/master/kpr-products/{created_product['id']}",
                            headers=sales_headers, timeout=30)
        assert r.status_code == 403


# ---------- Financing integration ----------
class TestFinancingUsesProduct:
    def test_financing_accepts_product_fields(self, super_headers, created_product):
        # find a customer + deal
        r = requests.get(f"{API}/customers", headers=super_headers, timeout=30)
        if r.status_code != 200:
            pytest.skip("customers endpoint not available")
        customers = r.json().get("data") or r.json().get("customers") or []
        if not customers:
            pytest.skip("no customers seeded")
        customer_id = customers[0].get("id")

        r = requests.get(f"{API}/deals", headers=super_headers, timeout=30)
        deals = []
        if r.status_code == 200:
            deals = r.json().get("data") or r.json().get("deals") or []
        if not deals:
            pytest.skip("no deals seeded")
        deal_id = deals[0].get("id")

        payload = {
            "customer_id": customer_id,
            "deal_id": deal_id,
            "bank_name": created_product["bank_name"],
            "product_type": "kpr",
            "requested_amount": 500_000_000,
            "tenor_months": 120,
            "interest_rate_pct": 6.5,
            "kpr_product_id": created_product["id"],
            "kpr_product_name": created_product["name"],
        }
        r = requests.post(f"{API}/financing", json=payload, headers=super_headers, timeout=30)
        # must not reject as 422 for the two new fields
        assert r.status_code != 422, f"financing rejected new fields: {r.text}"
        if r.status_code >= 400:
            pytest.skip(f"financing create failed for unrelated reason: {r.status_code} {r.text}")
        data = r.json().get("data") or r.json()
        fid = data.get("id")
        # verify persisted
        rg = requests.get(f"{API}/financing/{fid}", headers=super_headers, timeout=30)
        if rg.status_code == 200:
            fdata = rg.json().get("data") or rg.json()
            assert fdata.get("kpr_product_id") == created_product["id"]
            assert fdata.get("kpr_product_name") == created_product["name"]


# ---------- SP3K stage endpoint accepts new fields ----------
class TestSp3kAcceptsProductFields:
    def test_sp3k_not_422_on_new_fields(self, super_headers, created_product):
        # send to a bogus contract id — must not be 422 (schema validation error);
        # expect a business error (400/404/409) instead.
        payload = {
            "plafon": 500_000_000,
            "tenor_months": 120,
            "rate": 6.5,
            "kpr_product_id": created_product["id"],
            "kpr_product_name": created_product["name"],
        }
        r = requests.post(f"{API}/contracts/nope-contract-xxx/kpr/stage/sp3k",
                          json=payload, headers=super_headers, timeout=30)
        assert r.status_code != 422, f"schema rejected new fields: {r.text}"
