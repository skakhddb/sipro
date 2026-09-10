"""Sesi impor mentah: berkas Excel diparse → disimpan di server (BACKUP_DIR) → divalidasi →
sel bisa disunting di browser → commit (update per kunci / replace) dengan snapshot pengaman."""
import json
import logging
from pathlib import Path

from db import db
from core_utils import new_id, now_iso
from data_mgmt_backup import backup_dir, save_snapshot
from data_mgmt_full_export import parse_full_workbook
from data_mgmt_full_schema import EXCLUDED, org_filter
from data_mgmt_full_validate import validate_sheet, parsed_values, key_query, row_key
from data_mgmt_full_checks import cross_checks
from data_mgmt_full_report import build_report_workbook
import masterplan

logger = logging.getLogger("sipro.data_mgmt.full")
_REPORTS = {}  # sid → laporan validasi (cache; kadaluarsa saat sesi disunting)
MASTERPLAN_COLLS = {"projects", "clusters", "blocks", "units"}


def _path(org: str, sid: str) -> Path:
    d = backup_dir(org) / "import_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sid}.json"


async def create_session(content: bytes, org: str, actor: str, filename: str) -> dict:
    sheets = parse_full_workbook(content)
    if not sheets:
        raise ValueError("Tidak ada sheet data yang bisa dibaca.")
    sid = new_id()
    payload = {"id": sid, "org_id": org, "filename": filename, "created_by": actor,
               "created_at": now_iso(), "sheets": {}}
    for name, s in sheets.items():
        payload["sheets"][name] = {**s, "sheet": name}
    _path(org, sid).write_text(json.dumps(payload, ensure_ascii=False, default=str))
    rec = {"id": sid, "org_id": org, "filename": filename, "created_by": actor,
           "created_at": payload["created_at"], "status": "open",
           "sheets": [{"sheet": n, "collection": s["collection"], "rows": len(s["rows"])}
                      for n, s in sheets.items()]}
    await db.data_import_sessions.insert_one(dict(rec))
    rec.pop("_id", None)
    return rec


async def load_session(org: str, sid: str) -> dict:
    p = _path(org, sid)
    if not p.exists():
        raise LookupError("Sesi impor tidak ditemukan (mungkin sudah dibersihkan).")
    return json.loads(p.read_text())


def _save(org: str, payload: dict):
    _path(org, payload["id"]).write_text(json.dumps(payload, ensure_ascii=False, default=str))
    _REPORTS.pop(payload["id"], None)


async def list_sessions(org: str) -> list:
    return await db.data_import_sessions.find({"org_id": org}, {"_id": 0}).sort("created_at", -1).to_list(30)


async def delete_session(org: str, sid: str):
    _path(org, sid).unlink(missing_ok=True)
    _REPORTS.pop(sid, None)
    await db.data_import_sessions.delete_one({"id": sid, "org_id": org})


async def apply_edits(org: str, sid: str, edits: list) -> dict:
    """edits = [{sheet, row, col, value}] — value None mengosongkan sel; row baru dibuat bila belum ada."""
    payload = await load_session(org, sid)
    applied = 0
    for e in edits:
        s = payload["sheets"].get(e["sheet"])
        if not s or e["col"] not in s["columns"]:
            continue
        target = next((r for r in s["rows"] if r["row"] == e["row"]), None)
        if not target:
            target = {"row": e["row"], "cells": {}}
            s["rows"].append(target)
            s["rows"].sort(key=lambda r: r["row"])
        target["cells"][e["col"]] = e.get("value")
        applied += 1
    _save(org, payload)
    return {"applied": applied}


async def delete_rows(org: str, sid: str, sheet: str, rows: list) -> dict:
    payload = await load_session(org, sid)
    s = payload["sheets"].get(sheet)
    if not s:
        raise LookupError("Sheet tidak ada dalam sesi.")
    before = len(s["rows"])
    s["rows"] = [r for r in s["rows"] if r["row"] not in set(rows)]
    _save(org, payload)
    return {"deleted": before - len(s["rows"])}


async def report(org: str, sid: str) -> dict:
    if sid in _REPORTS:
        return _REPORTS[sid]
    payload = await load_session(org, sid)
    known = {n for n in await db.list_collection_names() if n not in EXCLUDED}
    file_ids = {}
    for s in payload["sheets"].values():
        ids = {str(r["cells"]["id"]) for r in s["rows"] if r["cells"].get("id")}
        file_ids.setdefault(s["collection"], set()).update(ids)
    sheets = [await validate_sheet(s, org, known, file_ids) for s in payload["sheets"].values()]
    checks = await cross_checks(org, sheets)
    totals = {"rows": 0, "insert": 0, "update": 0, "same": 0, "error": 0, "warning": 0, "info": 0,
              "suggestion": 0, "missing": 0, "checks": len(checks)}
    for s in sheets:
        totals["rows"] += s["total"]
        totals["missing"] += s["missing_count"]
        for k in ("insert", "update", "same", "error", "warning", "info", "suggestion"):
            totals[k] += s["counts"][k]
        if any(i["level"] == "error" for i in s["issues"]):
            totals["error"] += 1
    rep = {"id": sid, "filename": payload["filename"], "created_at": payload["created_at"],
           "sheets": sheets, "totals": totals, "checks": checks}
    _REPORTS[sid] = rep
    return rep


async def report_xlsx(org: str, sid: str) -> bytes:
    payload = await load_session(org, sid)
    return build_report_workbook(payload, await report(org, sid))


def sheet_page(rep: dict, sheet: str, offset: int, limit: int, only_issues: bool,
               status: str = None) -> dict:
    s = next((x for x in rep["sheets"] if x["sheet"] == sheet), None)
    if not s:
        raise LookupError("Sheet tidak ada dalam sesi.")
    rows = s["rows"]
    if only_issues:
        rows = [r for r in rows if r["issues"]]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return {**{k: v for k, v in s.items() if k != "rows"}, "filtered": len(rows),
            "offset": offset, "rows": rows[offset:offset + limit]}


async def commit(org: str, sid: str, actor: str, mode: str, sheets: list, skip_errors: bool,
                 actor_user: dict) -> dict:
    if mode not in ("update", "replace"):
        raise ValueError("Mode harus 'update' atau 'replace'.")
    rep = await report(org, sid)
    chosen = [s for s in rep["sheets"] if (not sheets or s["sheet"] in sheets) and s["known"]]
    if not chosen:
        raise ValueError("Tidak ada sheet yang bisa diimpor.")
    if not skip_errors and any(s["counts"]["error"] for s in chosen):
        raise ValueError("Masih ada baris error. Perbaiki dulu, atau centang 'lewati baris error'.")
    snap = await save_snapshot(org, actor, True, "pra-impor-semua-data", kind="auto")
    result, touched_projects = {}, False
    for s in chosen:
        coll, cols, types = s["collection"], s["columns"], s["types"]
        r = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0, "deleted": 0}
        keys = set()
        for row in s["rows"]:
            kind, key = row_key(row["cells"])
            if key:
                keys.add(key)
            if row["status"] == "error":
                r["skipped"] += 1
                continue
            if row["status"] == "same":
                r["unchanged"] += 1
                continue
            vals = parsed_values(row, types, cols)
            if row["status"] == "update":
                patch = {c: vals[c] for c in row["changed"] if c in vals}
                if coll not in ("orgs", "permission_settings"):
                    patch.pop("org_id", None)
                q = key_query(kind, key, coll, org)
                if patch and q:
                    await db[coll].update_one(q, {"$set": patch})
                    r["updated"] += 1
                else:
                    r["unchanged"] += 1
            else:
                doc = {k: v for k, v in vals.items() if v is not None}
                if kind == "_id":
                    doc["_id"] = key
                else:
                    doc["id"] = key or new_id()
                    keys.add(doc["id"])
                if coll not in ("orgs", "permission_settings"):
                    doc["org_id"] = org
                doc.setdefault("created_at", now_iso())
                await db[coll].insert_one(doc)
                r["inserted"] += 1
        if mode == "replace":
            q = org_filter(coll, org)
            async for d in db[coll].find(q, {"_id": 1, "id": 1, "role": 1}):
                k = str(d.get("id") or d["_id"])
                if k in keys:
                    continue
                if coll == "users" and (d.get("id") == actor_user.get("id") or d.get("role") == "super_admin"):
                    continue
                await db[coll].delete_one({"_id": d["_id"]})
                r["deleted"] += 1
        if coll in MASTERPLAN_COLLS and (r["inserted"] or r["updated"] or r["deleted"]):
            touched_projects = True
        result[coll] = r
    if touched_projects:
        async for p in db.projects.find({"org_id": org}, {"_id": 0, "id": 1}):
            await masterplan.recompute_stats(p["id"], org)
    total = {k: sum(r[k] for r in result.values()) for k in ("inserted", "updated", "unchanged", "skipped", "deleted")}
    await db.data_import_sessions.update_one({"id": sid, "org_id": org}, {"$set": {
        "status": "committed", "committed_at": now_iso(), "committed_by": actor, "mode": mode,
        "result": result, "snapshot_before": snap["id"]}})
    _REPORTS.pop(sid, None)
    logger.warning("IMPOR SEMUA DATA %s oleh %s (org %s): %s", mode, actor, org, total)
    return {"mode": mode, "collections": result, "totals": total, "snapshot_before": snap}
