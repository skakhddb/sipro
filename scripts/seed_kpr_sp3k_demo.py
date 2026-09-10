"""Seed contoh: satu kontrak KPR yang berhenti TEPAT di depan tahap SP3K, supaya dialog
"Catat SP3K" (pemilih Produk KPR) bisa diuji langsung di layar.

Rantai lewat API sungguhan (tidak menulis DB langsung): lead → SLIK lolos berbukti → reservasi
→ booking fee → booking → konversi skema KPR → tahap 'diajukan_ke_bank' (bank BTN) →
'appraisal' (bila diaktifkan konfigurasi). Produk KPR BTN dipastikan ada.

Jalankan: python3 scripts/seed_kpr_sp3k_demo.py   (backend lokal :8001, sandi seed)
"""
import sys
import time

import requests

BASE = "http://localhost:8001/api"
PW = "Sipro#2026"
BANK = "BTN"


def j(r):
    try:
        return r.json()
    except ValueError:
        return {}


def must(r, label):
    if r.status_code != 200:
        raise SystemExit(f"GAGAL {label}: {r.status_code} {r.text[:300]}")
    return j(r).get("data") or {}


def main() -> int:
    r = requests.post(f"{BASE}/auth/login", json={"email": "superadmin@sipro.co.id", "password": PW}, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"login gagal: {r.text[:200]}")
    h = {"Authorization": f"Bearer {j(r)['access_token']}"}
    tanda = str(int(time.time()))[-6:]

    # Produk KPR untuk bank ini (409 = sudah ada, aman).
    rp = requests.post(f"{BASE}/master/kpr-products", headers=h, timeout=30, json={
        "bank_name": BANK, "name": "KPR Subsidi FLPP", "tenors": [120, 180, 240],
        "interest_rate_pct": 5, "fixed_years": 20, "min_dp_pct": 1, "notes": "Rumah subsidi"})
    print("produk KPR:", "dibuat" if rp.status_code == 200 else f"{rp.status_code} (sudah ada)")

    units = must(requests.get(f"{BASE}/units", headers=h, params={"status": "available", "limit": 3}, timeout=30), "units")
    if not units:
        raise SystemExit("Tidak ada unit tersedia — seed proyek/unit dulu.")
    unit = units[0]

    lead = must(requests.post(f"{BASE}/leads", headers=h, timeout=30, json={
        "name": f"Demo KPR SP3K {tanda}", "phone": f"62811{tanda}9", "source": "walk_in"}), "lead")
    up = requests.post(f"{BASE}/files/upload", headers=h, timeout=120,
                       files={"file": ("ideb-demo.pdf", b"%PDF-1.4 iDeb SLIK demo\n", "application/pdf")},
                       data={"owner_type": "lead", "owner_id": lead["id"], "optimize": "false"})
    fid = must(up, "upload iDeb")["id"]
    must(requests.post(f"{BASE}/leads/{lead['id']}/slik-prescreen", headers=h, timeout=30,
                       json={"status": "clear", "note": "Kolektibilitas 1 (demo)", "evidence_file_ids": [fid]}), "slik")
    deal = must(requests.post(f"{BASE}/deals/reserve", headers=h, timeout=30,
                              json={"lead_id": lead["id"], "unit_id": unit["id"], "booking_fee": 5000000}), "reserve")
    requests.post(f"{BASE}/booking-fee/deals/{deal['id']}/pay", headers=h, timeout=30,
                  json={"amount": 5000000, "method": "transfer"})
    must(requests.post(f"{BASE}/deals/{deal['id']}/book", headers=h, json={}, timeout=30), "book")
    out = must(requests.post(f"{BASE}/deals/{deal['id']}/convert", headers=h, timeout=30,
                             json={"scheme": "kpr", "nik": f"3299{tanda}00001", "address": "Jl. Demo KPR"}), "convert")
    cust, contract = out.get("customer") or {}, out.get("contract") or {}
    cid = contract["id"]

    for stage, body in (("diajukan_ke_bank", {"bank": BANK, "note": "Berkas diserahkan ke bank"}),
                        ("appraisal", {"amount": int(unit.get("price") or 300000000), "note": "Appraisal bank"})):
        r = requests.post(f"{BASE}/contracts/{cid}/kpr/stage/{stage}", headers=h, json=body, timeout=30)
        print(f"tahap {stage}:", r.status_code, (j(r).get("detail") or "")[:80])
    kv = must(requests.get(f"{BASE}/contracts/{cid}/kpr", headers=h, timeout=30), "kpr")
    print("\n=== KONTRAK KPR DEMO ===")
    print("contract_id :", cid)
    print("customer_id :", cust.get("id"))
    print("unit        :", unit.get("code"))
    print("tahap KPR   :", kv.get("stage"), "→ berikutnya:", kv.get("next_stage"))
    print(f"URL         : /customers/{cust.get('id')}?tab=kontrak53")
    return 0 if kv.get("next_stage") == "sp3k" else 1


if __name__ == "__main__":
    sys.exit(main())
