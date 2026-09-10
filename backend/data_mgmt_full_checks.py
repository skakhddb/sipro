"""Cek konsistensi silang antar-koleksi sebelum impor: piutang (AR) vs harga deal/kontrak.

Dokumen dinilai dalam keadaan SETELAH impor: baris sheet menimpa dokumen DB ber-id sama.
"""
from db import db
from data_mgmt_full_validate import parsed_values

TOL = 1  # rupiah — toleransi pembulatan


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return None


def _rp(v):
    return f"Rp{int(round(v)):,}".replace(",", ".")


async def _merged(coll: str, org: str, report_sheet: dict | None, ids: set | None = None) -> dict:
    """{id: doc} dari DB (dibatasi ids bila ada), ditimpa nilai baris sheet."""
    q = {"org_id": org}
    if ids is not None:
        q["id"] = {"$in": list(ids)}
    out = {d["id"]: d async for d in db[coll].find(q, {"_id": 0}) if d.get("id")}
    for r in (report_sheet or {}).get("rows", []):
        if r["status"] == "error" or not r.get("key"):
            continue
        vals = parsed_values(r, report_sheet["types"], report_sheet["columns"])
        doc = {**out.get(r["key"], {"id": r["key"]}), **vals}
        doc["_sheet_row"] = r["row"]
        out[r["key"]] = doc
    return out


def _check_ar(ar: dict, deal: dict | None, contract: dict | None) -> list:
    msgs = []
    items = ar.get("items") if isinstance(ar.get("items"), list) else []
    unit_items = [i for i in items if isinstance(i, dict) and i.get("basis") != "addon"]
    sum_unit = sum(_num(i.get("amount")) or 0 for i in unit_items)
    sum_all = sum(_num(i.get("amount")) or 0 for i in items if isinstance(i, dict))
    sum_paid = sum(_num(i.get("paid_amount")) or 0 for i in items if isinstance(i, dict))
    total, unit_total = _num(ar.get("total")), _num(ar.get("unit_total"))
    paid, outstanding = _num(ar.get("paid")), _num(ar.get("outstanding"))
    if unit_total is not None and abs(sum_unit - unit_total) > TOL:
        msgs.append(("AR_UNIT_SUM", f"Σ termin unit {_rp(sum_unit)} ≠ unit_total {_rp(unit_total)}."))
    if total is not None and abs(sum_all - total) > TOL:
        msgs.append(("AR_TOTAL_SUM", f"Σ semua termin {_rp(sum_all)} ≠ total {_rp(total)}."))
    if paid is not None and abs(sum_paid - paid) > TOL:
        msgs.append(("AR_PAID_SUM", f"Σ paid_amount termin {_rp(sum_paid)} ≠ paid {_rp(paid)}."))
    if total is not None and paid is not None and outstanding is not None \
            and abs((total - paid) - outstanding) > TOL:
        msgs.append(("AR_OUTSTANDING", f"total − paid = {_rp(total - paid)} ≠ outstanding {_rp(outstanding)}."))
    if deal:
        pricing = deal.get("pricing") if isinstance(deal.get("pricing"), dict) else {}
        price = _num(pricing.get("net_price")) if pricing.get("net_price") is not None else _num(deal.get("price"))
        if price is not None and abs(sum_unit - price) > TOL:
            msgs.append(("AR_VS_DEAL", f"Σ termin unit {_rp(sum_unit)} ≠ harga deal/kontrak {_rp(price)} "
                         f"(deal {deal.get('unit_code') or deal.get('id')})."))
        if deal.get("unit_id") and ar.get("unit_id") and deal["unit_id"] != ar["unit_id"]:
            msgs.append(("AR_UNIT_MISMATCH", "unit_id AR berbeda dengan unit_id deal."))
    elif ar.get("deal_id"):
        msgs.append(("AR_DEAL_MISSING", f"deal_id {ar['deal_id']} tidak ditemukan."))
    if contract and contract.get("unit_id") and ar.get("unit_id") and contract["unit_id"] != ar["unit_id"]:
        msgs.append(("AR_CONTRACT_UNIT", f"unit_id kontrak {contract.get('number')} berbeda dengan AR."))
    return msgs


async def cross_checks(org: str, sheets: list) -> list:
    """→ [{code, level, sheet, row, key, message}] untuk AR yang ada di sheet atau deal-nya di sheet."""
    by_coll = {s["collection"]: s for s in sheets if s["known"]}
    ar_sheet, deal_sheet, ctr_sheet = by_coll.get("ar_invoices"), by_coll.get("deals"), by_coll.get("contracts")
    if not (ar_sheet or deal_sheet or ctr_sheet):
        return []
    deal_ids = {r["key"] for r in (deal_sheet or {}).get("rows", []) if r.get("key")}
    ars = await _merged("ar_invoices", org, ar_sheet, None if ar_sheet else set())
    if deal_ids:
        extra = await _merged("ar_invoices", org, None)
        ars.update({k: v for k, v in extra.items() if v.get("deal_id") in deal_ids and k not in ars})
    need_deals = {a.get("deal_id") for a in ars.values() if a.get("deal_id")} | deal_ids
    deals = await _merged("deals", org, deal_sheet, need_deals)
    contracts = await _merged("contracts", org, ctr_sheet, None)
    ctr_by_deal = {c.get("deal_id"): c for c in contracts.values()}
    out = []
    for ar in ars.values():
        deal = deals.get(ar.get("deal_id"))
        for code, msg in _check_ar(ar, deal, ctr_by_deal.get(ar.get("deal_id"))):
            in_sheet = "_sheet_row" in ar
            out.append({"code": code, "level": "warning", "key": ar["id"],
                        "sheet": ar_sheet["sheet"] if in_sheet and ar_sheet else None,
                        "row": ar.get("_sheet_row"), "collection": "ar_invoices",
                        "label": f"AR {ar.get('unit_code') or ''} {ar.get('lead_name') or ''}".strip(),
                        "message": msg})
    return out
