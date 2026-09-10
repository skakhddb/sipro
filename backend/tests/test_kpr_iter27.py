"""Iteration 27 backend tests: KPR import preview (dry-run), amend-terms, portal KPR, schedule."""
import io
import os
import time
import subprocess

import pytest
import requests
from openpyxl import Workbook

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://sipro-resumed.preview.emergentagent.com").rstrip("/") + "/api"
LOCAL = "http://localhost:8001/api"
PW = "Sipro#2026"


def _login(email, base=BASE):
    r = requests.post(f"{base}/auth/login", json={"email": email, "password": PW}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login('superadmin@sipro.co.id')}"}


@pytest.fixture(scope="module")
def sales_h():
    return {"Authorization": f"Bearer {_login('sales@sipro.co.id')}"}


def _btn_product(admin_h):
    r = requests.get(f"{BASE}/master/kpr-products", headers=admin_h, params={"bank_name": "BTN"}, timeout=30)
    items = r.json().get("data") or []
    if isinstance(items, dict):
        items = items.get("items", [])
    for p in items:
        if p.get("name") == "KPR Subsidi FLPP":
            return p
    for p in items:
        if p.get("bank_name") == "BTN":
            return p
    return None


# ---- Excel import preview (dry-run) ----
def _build_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    headers = ["bank_name", "name", "tenors", "interest_rate_pct", "fixed_years",
               "floating_rate_pct", "min_dp_pct", "notes", "is_active"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestImportPreview:
    def test_dry_run_then_commit(self, admin_h):
        ts = str(int(time.time()))
        new_name = f"CIMB Test {ts}"
        rows = [
            {"bank_name": "CIMB Niaga", "name": new_name, "tenors": "120,180",
             "interest_rate_pct": 6.5, "fixed_years": 3, "floating_rate_pct": 10,
             "min_dp_pct": 10, "notes": "test", "is_active": True},
            # update existing BTN — change rate but restore after
            {"bank_name": "BTN", "name": "KPR Subsidi FLPP", "tenors": "120,180,240",
             "interest_rate_pct": 5.25, "fixed_years": 20, "min_dp_pct": 1,
             "notes": "Rumah subsidi", "is_active": True},
            # invalid: missing name
            {"bank_name": "Bank X", "name": "", "tenors": "120",
             "interest_rate_pct": 7, "is_active": True},
        ]
        buf = _build_xlsx(rows)

        # count before
        r0 = requests.get(f"{BASE}/master/kpr-products", headers=admin_h, timeout=30)
        items_before = (r0.json().get("data") or {})
        if isinstance(items_before, dict):
            items_before = items_before.get("items", [])
        count_before = len(items_before)

        # DRY-RUN
        buf.seek(0)
        r = requests.post(
            f"{BASE}/master/kpr-products/import",
            headers=admin_h, params={"dry_run": "true"},
            files={"file": ("kpr.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json().get("data") or r.json()
        assert "preview" in data, data
        preview = data["preview"]
        # find rows
        creates = [p for p in preview if p.get("action") == "create"]
        updates = [p for p in preview if p.get("action") == "update"]
        assert any(p["name"] == new_name for p in creates), preview
        upd = next((p for p in updates if p.get("bank_name") == "BTN"), None)
        assert upd is not None, preview
        assert "changes" in upd
        assert any("interest_rate_pct" in str(c) for c in upd["changes"]), upd
        # errors row
        assert data.get("errors"), data
        # Nothing written
        r1 = requests.get(f"{BASE}/master/kpr-products", headers=admin_h, timeout=30)
        items_after = r1.json().get("data") or {}
        if isinstance(items_after, dict):
            items_after = items_after.get("items", [])
        assert len(items_after) == count_before, "dry-run must not create rows"
        assert not any(p.get("name") == new_name for p in items_after)

        # COMMIT — restore BTN rate to 5 and include only valid rows
        rows_commit = [
            {"bank_name": "CIMB Niaga", "name": new_name, "tenors": "120,180",
             "interest_rate_pct": 6.5, "fixed_years": 3, "floating_rate_pct": 10,
             "min_dp_pct": 10, "notes": "test", "is_active": True},
            {"bank_name": "BTN", "name": "KPR Subsidi FLPP", "tenors": "120,180,240",
             "interest_rate_pct": 5, "fixed_years": 20, "min_dp_pct": 1,
             "notes": "Rumah subsidi", "is_active": True},
        ]
        buf2 = _build_xlsx(rows_commit)
        r2 = requests.post(
            f"{BASE}/master/kpr-products/import",
            headers=admin_h,
            files={"file": ("kpr.xlsx", buf2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=60,
        )
        assert r2.status_code == 200, r2.text
        d2 = r2.json().get("data") or r2.json()
        # response varies — accept either counters or preview echo
        ok = False
        for k in ("created", "updated", "to_create", "to_update"):
            v = d2.get(k)
            if isinstance(v, int) and v >= 0:
                ok = True
            if isinstance(v, list) and len(v) >= 0:
                ok = True
        assert ok, d2

        # verify list contains new product
        r3 = requests.get(f"{BASE}/master/kpr-products", headers=admin_h, timeout=30)
        items3 = r3.json().get("data") or {}
        if isinstance(items3, dict):
            items3 = items3.get("items", [])
        created = next((p for p in items3 if p.get("name") == new_name), None)
        assert created is not None
        # cleanup
        try:
            requests.delete(f"{BASE}/master/kpr-products/{created['id']}", headers=admin_h, timeout=30)
        except Exception:
            pass

    def test_sales_forbidden_on_dry_run(self, sales_h):
        buf = _build_xlsx([{"bank_name": "X", "name": "Y", "tenors": "120", "interest_rate_pct": 5}])
        r = requests.post(
            f"{BASE}/master/kpr-products/import",
            headers=sales_h, params={"dry_run": "true"},
            files={"file": ("k.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=30,
        )
        assert r.status_code == 403, r.text


# ---- Amend-terms flow ----
def _seed_sp3k_gate():
    """Run the seed script; return (contract_id, customer_id, phone)."""
    out = subprocess.run(["python3", "/app/scripts/seed_kpr_sp3k_demo.py"], capture_output=True, text=True, timeout=120)
    text = out.stdout + "\n" + out.stderr
    cid = None
    custid = None
    for line in text.splitlines():
        if "contract_id" in line:
            cid = line.split(":", 1)[1].strip()
        elif "customer_id" in line:
            custid = line.split(":", 1)[1].strip()
    assert cid and custid, f"seed failed: {text}"
    return cid, custid


class TestAmendTerms:
    def test_full_flow(self, admin_h, sales_h):
        cid, custid = _seed_sp3k_gate()

        # amend before SP3K → 400
        r = requests.post(f"{BASE}/contracts/{cid}/kpr/amend-terms", headers=admin_h,
                          json={"tenor_months": 180, "rate": 5, "reason": "test aja pak"}, timeout=30)
        assert r.status_code == 400
        assert "SP3K" in r.text

        # upload SP3K file
        up = requests.post(f"{BASE}/files/upload", headers=admin_h,
                           files={"file": ("sp3k.pdf", b"%PDF-1.4 sp3k demo\n", "application/pdf")},
                           data={"owner_type": "contract", "owner_id": cid, "optimize": "false"}, timeout=60)
        assert up.status_code == 200
        file_id = (up.json().get("data") or {}).get("id")
        assert file_id

        # get BTN product id
        btn = _btn_product(admin_h)
        assert btn, "BTN product missing"

        # record SP3K
        r = requests.post(f"{BASE}/contracts/{cid}/kpr/stage/sp3k", headers=admin_h,
                          json={"number": f"SP3K-{int(time.time())}", "plafon": 250000000,
                                "tenor_months": 240, "rate": 5, "file_id": file_id,
                                "kpr_product_id": btn["id"], "kpr_product_name": "KPR Subsidi FLPP"},
                          timeout=30)
        assert r.status_code == 200, r.text

        # sales forbidden
        rf = requests.post(f"{BASE}/contracts/{cid}/kpr/amend-terms", headers=sales_h,
                           json={"tenor_months": 180, "rate": 5, "kpr_product_id": btn["id"],
                                 "kpr_product_name": "KPR Subsidi FLPP", "reason": "pembeli minta"}, timeout=30)
        print("SALES amend status=", rf.status_code, rf.text[:200])
        # report actual — expected 403
        assert rf.status_code in (401, 403)

        # identical values → 400
        r = requests.post(f"{BASE}/contracts/{cid}/kpr/amend-terms", headers=admin_h,
                          json={"tenor_months": 240, "rate": 5, "kpr_product_id": btn["id"],
                                "kpr_product_name": "KPR Subsidi FLPP", "reason": "tidak ada perubahan"}, timeout=30)
        assert r.status_code == 400, r.text
        assert "berubah" in r.text.lower() or "tidak" in r.text.lower()

        # short reason → 400
        r = requests.post(f"{BASE}/contracts/{cid}/kpr/amend-terms", headers=admin_h,
                          json={"tenor_months": 180, "rate": 5, "kpr_product_id": btn["id"],
                                "kpr_product_name": "KPR Subsidi FLPP", "reason": "a"}, timeout=30)
        assert r.status_code in (400, 422), r.text

        # valid amend
        r = requests.post(f"{BASE}/contracts/{cid}/kpr/amend-terms", headers=admin_h,
                          json={"tenor_months": 180, "rate": 5, "kpr_product_id": btn["id"],
                                "kpr_product_name": "KPR Subsidi FLPP",
                                "reason": "Pembeli memperpendek tenor"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json().get("data") or r.json()
        assert data.get("tenor_months") == 180
        sp3k = data.get("sp3k") or {}
        assert sp3k.get("tenor") == 180 or sp3k.get("tenor_months") == 180
        amends = data.get("terms_amendments") or []
        assert len(amends) == 1
        before = amends[0].get("before") or {}
        after = amends[0].get("after") or {}
        assert before.get("tenor_months") == 240
        assert after.get("tenor_months") == 180

        # schedule
        r = requests.get(f"{BASE}/contracts/{cid}/kpr/schedule", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        sd = r.json().get("data") or r.json()
        assert sd.get("available") is True
        assert sd.get("tenor_months") == 180
        assert sd.get("fixed_installment") == 1976984, sd.get("fixed_installment")
        assert len(sd.get("rows") or []) == 15
        assert sd["rows"][-1]["balance_end"] == 0
        assert len(sd.get("amendments") or []) == 1

        # stash for portal test
        pytest.contract_ready = (cid, custid)


# ---- Portal KPR ----
class TestPortalKpr:
    def test_portal_kpr_with_sp3k(self, admin_h):
        cid, custid = getattr(pytest, "contract_ready", (None, None))
        if not cid:
            pytest.skip("no contract from amend test")
        # get phone
        r = requests.get(f"{BASE}/customers/{custid}", headers=admin_h, timeout=30)
        assert r.status_code == 200
        cust = r.json().get("data") or r.json()
        phone = cust.get("phone")
        assert phone

        # request OTP
        r = requests.post(f"{BASE}/portal/auth/request-otp", json={"identifier": phone}, timeout=30)
        assert r.status_code == 200, r.text
        r = requests.post(f"{BASE}/portal/auth/verify-otp",
                          json={"identifier": phone, "code": "123456"}, timeout=30)
        assert r.status_code == 200, r.text
        token = (r.json().get("data") or r.json()).get("access_token") or (r.json().get("data") or r.json()).get("token")
        assert token

        r = requests.get(f"{BASE}/portal/kpr", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json().get("data") or r.json()
        arr = data if isinstance(data, list) else data.get("items", [])
        assert arr, data
        entry = arr[0]
        assert entry.get("available") is True
        assert entry.get("bank_name") == "BTN"
        assert entry.get("product_name") == "KPR Subsidi FLPP"
        assert entry.get("plafon") == 250000000
        assert entry.get("tenor_months") == 180
        assert entry.get("fixed_installment") == 1976984
        assert len(entry.get("rows") or []) == 15
        assert "amendments" not in entry, "portal must not leak amendments"

    def test_portal_kpr_no_sp3k(self, admin_h):
        cid, custid = _seed_sp3k_gate()
        r = requests.get(f"{BASE}/customers/{custid}", headers=admin_h, timeout=30)
        phone = (r.json().get("data") or r.json()).get("phone")
        requests.post(f"{BASE}/portal/auth/request-otp", json={"identifier": phone}, timeout=30)
        r = requests.post(f"{BASE}/portal/auth/verify-otp",
                          json={"identifier": phone, "code": "123456"}, timeout=30)
        token = (r.json().get("data") or r.json()).get("access_token") or (r.json().get("data") or r.json()).get("token")
        r = requests.get(f"{BASE}/portal/kpr", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json().get("data") or r.json()
        arr = data if isinstance(data, list) else data.get("items", [])
        assert arr
        entry = arr[0]
        assert entry.get("available") is False
        reason = str(entry.get("reason") or entry.get("message") or "")
        assert "SP3K" in reason or "sp3k" in reason.lower(), entry


# ---- Schedule engine unit ----
class TestScheduleEngine:
    def test_yearly_schedule_mixed(self):
        import sys
        sys.path.insert(0, "/app")
        from backend.kpr_schedule import yearly_schedule
        r = yearly_schedule(300000000, 180, 6.75, 3, 11.5)
        assert r["fixed_installment"] == 2654728
        assert r["floating_installment"] == 3356170
        assert len(r["rows"]) == 15
        assert r["rows"][0]["phase"] == "fixed"
        assert r["rows"][2]["phase"] == "fixed"
        assert r["rows"][3]["phase"] == "floating"
        assert r["rows"][-1]["balance_end"] == 0

    def test_yearly_schedule_zero_rate(self):
        import sys
        sys.path.insert(0, "/app")
        from backend.kpr_schedule import yearly_schedule
        r = yearly_schedule(120000000, 24, 0)
        assert r["fixed_installment"] == 5000000
        assert r["total_interest"] == 0
