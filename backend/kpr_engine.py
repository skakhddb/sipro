"""SUB-ALUR KPR (Fase 53D) — berkas → bank → appraisal → SP3K → AKAD KREDIT → pencairan.

## Cacat NYATA yang ditutup berkas ini

Pemilik produk menulis: *"AJB itu ketika akad kredit, seharusnya ini sudah di tahap
customer"*. Sebelum Fase 53 kata **akad kredit** tidak ada sama sekali di data: `financing_apps`
hanya punya `status` bergaya administratif (`draft/submitted/approved/rejected/disbursing/done`),
tanpa tempat menyimpan SP3K, akta akad, maupun pencairan — sehingga "sudah akad atau belum"
hanya ada di kepala orang, dan `POST /deals/{id}/ajb` malah menuntut PPJB lalu BAST (aturan
skema TUNAI) untuk pembelian yang jelas-jelas KPR.

Sekarang tahap KPR memakai kosakata SSOT `kpr_stage` (sudah ada sejak Fase 39, tetapi belum
pernah dipakai) dan setiap tahap punya GERBANG BUKTI:

  * `sp3k`        → wajib berkas SP3K + plafon yang DISETUJUI bank (bukan plafon usulan);
  * `akad_kredit` → wajib SP3K sah + (bila ada kelebihan tanah) SPKT terbit & kelebihan
                    tanah LUNAS, sesuai ketentuan dokumen owner;
  * `pencairan`   → wajib akad yang sudah tercatat.

Tahap `akad_kredit` juga MENULIS tahap legal kontrak (keputusan owner D4: legal milik
pembeli), sehingga AJB pada skema KPR menyusul akad — bukan menunggu serah terima kunci.
"""
import logging

import reference as ref
import settings_store as cfg
from core_utils import due_in, new_id, now_iso
from db import db
from engine import add_activity, auto_create_task

logger = logging.getLogger("sipro.kpr")

KPR_ORDER = ("berkas_lengkap", "diajukan_ke_bank", "appraisal", "sp3k", "akad_kredit",
             "pencairan")


def _rp(v) -> str:
    return f"Rp {int(v or 0):,}".replace(",", ".")


async def _kpr_app(org: str, contract: dict) -> dict:
    return await db.financing_apps.find_one({"org_id": org, "deal_id": contract["deal_id"]},
                                            {"_id": 0}, sort=[("created_at", -1)])


def _ce():
    """Impor malas `contracts_engine` — memutus siklus impor (kontrak ⇄ KPR)."""
    import contracts_engine as ce
    return ce


async def kpr_of(org: str, contract: dict) -> dict:
    """Pengajuan KPR untuk kontrak ini + tahap berikutnya yang boleh dimajukan."""
    if contract.get("scheme") != "kpr":
        return {"applicable": False, "reason": "Skema kontrak ini bukan KPR.",
                "application": None, "stages": []}
    app = await db.financing_apps.find_one(
        {"org_id": org, "deal_id": contract["deal_id"]}, {"_id": 0},
        sort=[("created_at", -1)])
    use_appraisal = bool(await cfg.get("kpr.use_appraisal_step", org_id=org))
    order = [s for s in KPR_ORDER if s != "appraisal" or use_appraisal]
    cur = (app or {}).get("kpr_stage")
    stages = []
    for s in order:
        done = bool(cur) and order.index(s) <= order.index(cur) if cur in order else False
        stages.append({"stage": s, "label": ref.label_of("kpr_stage", s), "done": done,
                       "current": s == cur})
    return {"applicable": True, "reason": None, "application": app, "stages": stages,
            "stage": cur, "stage_label": ref.label_of("kpr_stage", cur) if cur else None,
            "next_stage": next((s["stage"] for s in stages if not s["done"]), None)}



# ============================================================ sub-alur KPR
async def ensure_kpr_app(org: str, contract: dict, actor: str, bank: str = None) -> dict:
    """Pengajuan KPR lahir bersama kontrak KPR (D9) — tanpa itu tidak ada tempat menyimpan
    SP3K/akad/pencairan, dan "sudah akad atau belum" hanya ada di kepala orang."""
    if contract.get("scheme") != "kpr":
        raise ValueError("Kontrak ini bukan skema KPR.")
    app = await _kpr_app(org, contract)
    if app:
        return app
    ts = now_iso()
    bd = await _ce().build_breakdown(org, contract)
    doc = {
        "id": new_id(), "org_id": org, "deal_id": contract["deal_id"],
        "contract_id": contract["id"], "customer_id": contract.get("customer_id"),
        "unit_id": contract.get("unit_id"), "bank_name": bank or "",
        "plafon": int(bd.get("plafon_kredit") or 0),
        "requested_plafon": int(bd.get("plafon_kredit") or 0),
        "approved_plafon": 0, "dp_amount": 0, "tenor_months": 0, "interest_rate_pct": 0,
        "status": "draft", "kpr_stage": "berkas_lengkap",
        "stage_history": [{"from": None, "to": "berkas_lengkap", "at": ts, "actor": actor,
                           "reason": "Pengajuan dibuat bersama kontrak KPR"}],
        "sp3k": {}, "appraisal": {}, "akad": {}, "disbursement": {}, "rejection": {},
        "created_by": actor, "created_at": ts, "updated_at": ts,
    }
    await db.financing_apps.insert_one(dict(doc))
    doc.pop("_id", None)
    await add_activity(entity_type="customer", entity_id=contract.get("customer_id"),
                       type="system", actor=actor, org_id=org,
                       body=(f"Pengajuan KPR dibuka untuk unit {contract.get('unit_code')} "
                             "(tahap: berkas lengkap)."))
    return doc


async def kpr_advance(org: str, contract_id: str, stage: str, payload: dict,
                      actor: str, user: dict = None) -> dict:
    """Majukan tahap KPR dengan GERBANG BUKTI (SP3K wajib berkas + plafon; akad wajib SP3K)."""
    c = await _ce().get_raw(org, contract_id)
    if c.get("scheme") != "kpr":
        raise ValueError("Kontrak ini bukan skema KPR.")
    if stage not in KPR_ORDER and stage not in ("ditolak", "batal"):
        raise ValueError(f"Tahap KPR '{stage}' tidak dikenal.")
    existed = await db.financing_apps.find_one({"org_id": org, "deal_id": c["deal_id"]}, {"_id": 1})
    app = await ensure_kpr_app(org, c, actor, bank=payload.get("bank"))
    use_appraisal = bool(await cfg.get("kpr.use_appraisal_step", org_id=org))
    order = [s for s in KPR_ORDER if s != "appraisal" or use_appraisal]
    cur = app.get("kpr_stage") if existed else None
    if stage == "pencairan" and cur == "pencairan":
        # Multi-tranche (parsial/retensi): tahap pencairan boleh dicatat berulang.
        import kpr_disburse as kd
        return await kd.disburse(org, c, app, payload, user or {"email": actor, "role": None})
    # Belum ada tahap tercatat → satu-satunya langkah sah adalah tahap pertama. (Dulu
    # `cur` default "berkas_lengkap" sehingga tombol "Catat Berkas lengkap" di UI selalu
    # ditolak "sudah dilewati" — padahal status KPR bilang itu tahap berikutnya.)
    if stage in order and not cur and stage != order[0]:
        raise ValueError(f"Tahap sebelumnya belum selesai: {ref.label_of('kpr_stage', order[0])}.")
    if stage in order and cur in order and order.index(stage) <= order.index(cur):
        raise ValueError(f"Tahap {ref.label_of('kpr_stage', stage)} sudah dilewati.")
    if stage in order and cur in order and order.index(stage) > order.index(cur) + 1:
        lewat = order[order.index(cur) + 1]
        raise ValueError(f"Tahap sebelumnya belum selesai: "
                         f"{ref.label_of('kpr_stage', lewat)}.")
    ts = now_iso()
    setter = {"kpr_stage": stage, "updated_at": ts}
    # `kpr.sla_days` (Pusat Konfigurasi): tenggat tahap tersimpan agar bisa dilaporkan "tersangkut".
    sla_days = (await cfg.get("kpr.sla_days", org_id=org) or {})
    days = int((sla_days or {}).get(stage) or 0) if isinstance(sla_days, dict) else 0
    setter["kpr_stage_entered_at"] = ts
    setter["kpr_stage_sla_days"] = days or None
    setter["kpr_stage_due_at"] = due_in(days=days) if days else None
    extra_push = {}
    if payload.get("bank"):
        setter["bank_name"] = payload["bank"]
    if stage == "sp3k":
        if not payload.get("file_id"):
            raise ValueError("SP3K wajib disertai berkasnya (unggah dulu berkas SP3K).")
        if not int(payload.get("plafon") or 0):
            raise ValueError("Plafon yang DISETUJUI bank wajib diisi pada tahap SP3K.")
        setter["sp3k"] = {"number": payload.get("number"), "date": payload.get("date") or ts[:10],
                          "plafon": int(payload["plafon"]),
                          "tenor": int(payload.get("tenor_months") or 0),
                          "rate": float(payload.get("rate") or 0),
                          "valid_until": payload.get("valid_until"),
                          "product_id": payload.get("kpr_product_id"),
                          "product_name": payload.get("kpr_product_name"),
                          "file_id": payload["file_id"], "at": ts, "by": actor}
        setter["approved_plafon"] = int(payload["plafon"])
        setter["status"] = "approved"
        if payload.get("kpr_product_id"):
            setter["kpr_product_id"] = payload["kpr_product_id"]
            setter["kpr_product_name"] = payload.get("kpr_product_name")
        if payload.get("tenor_months"):
            setter["tenor_months"] = int(payload["tenor_months"])
        if payload.get("rate"):
            setter["interest_rate_pct"] = float(payload["rate"])
    if stage == "appraisal":
        setter["appraisal"] = {"done_at": payload.get("date") or ts[:10],
                              "value": int(payload.get("amount") or 0) or None,
                              "notes": payload.get("note"),
                              "file_id": payload.get("file_id"), "by": actor}
    if stage == "diajukan_ke_bank":
        setter["submission"] = {"submitted_at": ts, "submitted_by": actor,
                               "note": payload.get("note")}
        setter["status"] = "submitted"
    if stage == "akad_kredit":
        sp3k = app.get("sp3k") or {}
        if not (sp3k.get("file_id") and int(app.get("approved_plafon") or 0) > 0):
            raise ValueError("Akad kredit butuh SP3K yang sudah tercatat lengkap "
                             "(berkas + plafon disetujui).")
        bd = await _ce().build_breakdown(org, c)
        if bd.get("has_excess_land"):
            if (await cfg.get("addon.require_spkt_for_excess_land", org_id=org)
                    and not await _ce()._spkt_exists(org, c)):
                raise ValueError("Ada kelebihan tanah tetapi SPKT belum diterbitkan — "
                                 "dokumen itu syarat sebelum akad.")
            if not await _ce()._excess_land_paid(org, c, bd):
                raise ValueError(f"Kelebihan tanah {_rp(bd.get('excess_land'))} wajib lunas "
                                 "sebelum akad kredit (ketentuan SPKT).")
        setter["akad"] = {"date": payload.get("date") or ts[:10],
                          "notary": payload.get("notary"), "place": payload.get("place"),
                          "file_id": payload.get("file_id"), "at": ts, "by": actor}
    if stage == "pencairan":
        # Fase 78: pencairan = TAHAPAN terkonfigurasi + validasi (tagihan terbit, ≤ outstanding,
        # ≤ plafon, tahap tidak 2×) + kuitansi `kpr` + jurnal. Mesinnya di `kpr_disburse`.
        import kpr_disburse as kd
        return await kd.disburse(org, c, app, payload, user or {"email": actor, "role": None})
    await db.financing_apps.update_one({"id": app["id"]}, {
        "$set": setter,
        "$push": {"stage_history": {"from": cur, "to": stage, "at": ts, "actor": actor,
                                    "reason": payload.get("note"),
                                    "evidence": [payload.get("file_id")]
                                    if payload.get("file_id") else []}, **extra_push}})
    await add_activity(entity_type="customer", entity_id=c.get("customer_id"), type="system",
                       actor=actor, org_id=org,
                       body=(f"KPR unit {c.get('unit_code')} maju ke tahap "
                             f"{ref.label_of('kpr_stage', stage)}."))
    # Akad kredit adalah peristiwa LEGAL pembeli — kontraknya ikut mencatat (D4).
    if stage == "akad_kredit" and not (c.get("legal") or {}).get("akad_kredit"):
        await _ce().legal_advance(org, contract_id, "akad_kredit",
                            {"date": payload.get("date"), "notary": payload.get("notary"),
                             "place": payload.get("place"), "file_id": payload.get("file_id"),
                             "note": "Dicatat otomatis dari tahap akad kredit KPR."}, actor)
    return await db.financing_apps.find_one({"id": app["id"]}, {"_id": 0})


async def kpr_reject(org: str, contract_id: str, reason: str, file_id: str,
                     actor: str) -> dict:
    """Bank menolak: tahap `ditolak` + usul refund booking fee sesuai `[CFG]` (`[DOC]` 50%)."""
    c = await _ce().get_raw(org, contract_id)
    app = await ensure_kpr_app(org, c, actor)
    pct = float(await cfg.get("booking_fee.refund_kpr_rejected_pct", org_id=org) or 50)
    bd = await _ce().build_breakdown(org, c)
    refund = int(round(int(bd.get("booking_fee") or 0) * pct / 100))
    ts = now_iso()
    await db.financing_apps.update_one({"id": app["id"]}, {
        "$set": {"kpr_stage": "ditolak", "status": "rejected", "updated_at": ts,
                 "rejection": {"at": ts, "note": reason, "file_id": file_id,
                               "refund_pct": pct, "refund_amount": refund, "by": actor}},
        "$push": {"stage_history": {"from": app.get("kpr_stage"), "to": "ditolak", "at": ts,
                                    "actor": actor, "reason": reason,
                                    "evidence": [file_id] if file_id else []}}})
    await auto_create_task(
        source_event=f"kpr.rejected:{app['id']}",
        title=(f"Tindak lanjut KPR ditolak: {c.get('customer_name')} · usul refund booking "
               f"fee {pct:g}% = {_rp(refund)}"),
        type="follow_up", related_entity_type="contract", related_entity_id=contract_id,
        assigned_to=c.get("assigned_to"), due_date=due_in(days=3), priority="high",
        org_id=org)
    await add_activity(entity_type="customer", entity_id=c.get("customer_id"), type="system",
                       actor=actor, org_id=org,
                       body=(f"KPR ditolak bank — {reason}. Usul refund booking fee "
                             f"{pct:g}% ({_rp(refund)}) sesuai ketentuan SPR."))
    return await db.financing_apps.find_one({"id": app["id"]}, {"_id": 0})



async def amend_terms(org: str, contract_id: str, payload: dict, actor: str) -> dict:
    """Bank mengubah tenor/bunga/produk SESUDAH SP3K terbit: nilai lama disimpan di
    `terms_amendments` (bukan ditimpa diam-diam), nilai baru menjadi acuan jadwal angsuran."""
    c = await _ce().get_raw(org, contract_id)
    if c.get("scheme") != "kpr":
        raise ValueError("Kontrak ini bukan skema KPR.")
    app = await _kpr_app(org, c)
    if not app or not (app.get("sp3k") or {}).get("file_id"):
        raise ValueError("Amandemen hanya untuk pengajuan yang SP3K-nya sudah tercatat.")
    if app.get("kpr_stage") == "ditolak":
        raise ValueError("Pengajuan sudah ditolak bank — tidak ada tenor/bunga yang bisa diamandemen.")
    tenor = int(payload.get("tenor_months") or 0)
    rate = float(payload.get("rate") if payload.get("rate") is not None else -1)
    if tenor <= 0 or rate < 0:
        raise ValueError("Tenor (bulan) dan bunga (%/th) wajib diisi.")
    reason = (payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise ValueError("Alasan amandemen minimal 5 huruf (mis. 'Bank menurunkan bunga promo').")
    before = {"tenor_months": int(app.get("tenor_months") or 0), "interest_rate_pct": float(app.get("interest_rate_pct") or 0),
              "kpr_product_id": app.get("kpr_product_id"), "kpr_product_name": app.get("kpr_product_name")}
    after = {"tenor_months": tenor, "interest_rate_pct": rate,
             "kpr_product_id": payload.get("kpr_product_id") or None, "kpr_product_name": payload.get("kpr_product_name") or None}
    if before == after:
        raise ValueError("Tidak ada yang berubah — tenor, bunga, dan produk sama dengan sebelumnya.")
    ts = now_iso()
    entry = {"at": ts, "by": actor, "reason": reason, "file_id": payload.get("file_id"),
             "before": before, "after": after}
    await db.financing_apps.update_one({"id": app["id"]}, {
        "$set": {**after, "sp3k.tenor": tenor, "sp3k.rate": rate,
                 "sp3k.product_id": after["kpr_product_id"], "sp3k.product_name": after["kpr_product_name"],
                 "updated_at": ts},
        "$push": {"terms_amendments": entry}})
    await add_activity(entity_type="customer", entity_id=c.get("customer_id"), type="system",
                       actor=actor, org_id=org,
                       body=(f"Amandemen KPR: tenor {before['tenor_months']}→{tenor} bulan, bunga "
                             f"{before['interest_rate_pct']:g}→{rate:g}%/th"
                             + (f", produk {after['kpr_product_name']}" if after["kpr_product_name"] else "")
                             + f". Alasan: {reason}"))
    return await db.financing_apps.find_one({"id": app["id"]}, {"_id": 0})


async def schedule_of(org: str, contract: dict) -> dict:
    """Jadwal angsuran simulasi untuk pengajuan KPR kontrak (None bila SP3K belum tercatat)."""
    from kpr_schedule import yearly_schedule
    app = await _kpr_app(org, contract) if contract.get("scheme") == "kpr" else None
    if not app:
        return {"available": False, "reason": "Kontrak ini bukan skema KPR / belum ada pengajuan."}
    sp3k = app.get("sp3k") or {}
    plafon = int(app.get("approved_plafon") or 0)
    if not (sp3k.get("file_id") and plafon > 0 and int(app.get("tenor_months") or 0) > 0):
        return {"available": False, "reason": "Jadwal angsuran tersedia setelah SP3K bank tercatat (plafon & tenor).",
                "bank_name": app.get("bank_name"), "stage": app.get("kpr_stage")}
    prod = await db.kpr_products.find_one({"org_id": org, "id": app.get("kpr_product_id")}, {"_id": 0}) \
        if app.get("kpr_product_id") else None
    fixed_years = (prod or {}).get("fixed_years")
    floating = (prod or {}).get("floating_rate_pct")
    sched = yearly_schedule(plafon, app["tenor_months"], float(app.get("interest_rate_pct") or 0), fixed_years, floating)
    return {"available": True, "bank_name": app.get("bank_name"), "product_name": app.get("kpr_product_name"),
            "plafon": plafon, "tenor_months": int(app["tenor_months"]), "interest_rate_pct": float(app.get("interest_rate_pct") or 0),
            "fixed_years": fixed_years, "floating_rate_pct": floating, "stage": app.get("kpr_stage"),
            "stage_label": ref.label_of("kpr_stage", app.get("kpr_stage")),
            "sp3k": {"number": sp3k.get("number"), "date": sp3k.get("date"), "valid_until": sp3k.get("valid_until")},
            "amendments": app.get("terms_amendments") or [], **sched}
