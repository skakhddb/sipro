"""Validasi impor mentah: konversi sel per tipe, temuan (error/peringatan/info), saran koreksi
(hanya saran — diterapkan bila pengguna memilih), dan selisih terhadap dokumen di DB."""
import ast
import difflib
import json
import re
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from dateutil import parser as dtparser

from db import db
from core_utils import normalize_phone_e164
from data_mgmt_full_schema import (DATE_COL_RE, ENUM_COL_RE, KEEP_MARK, REF_MAP, TOO_LARGE,
                                   org_filter, sample_types, type_of)

_TRUE = {"true", "ya", "y", "1", "yes", "aktif", "benar"}
_FALSE = {"false", "tidak", "n", "0", "no", "nonaktif", "salah"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_PHONE_COL = re.compile(r"(^|_)(phone|hp|wa_number|whatsapp|mobile)$")
_EMAIL_COL = re.compile(r"(^|_)email$")


class Issue:
    def __init__(self, col, level, message, suggestion=None):
        self.col, self.level, self.message, self.suggestion = col, level, message, suggestion

    def out(self):
        d = {"col": self.col, "level": self.level, "message": self.message}
        if self.suggestion is not None:
            d["suggestion"] = self.suggestion
        return d


def _num_str(s: str):
    s2 = re.sub(r"(?i)rp|\s", "", s)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s2):      # 1.250.000,50 (format ID)
        s2 = s2.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s2):    # 1,250,000.50 (format EN)
        s2 = s2.replace(",", "")
    elif re.fullmatch(r"-?\d+,\d+", s2):
        s2 = s2.replace(",", ".")
    try:
        f = float(s2)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def _try_date(s: str):
    try:
        return dtparser.parse(s, dayfirst=True)
    except (ValueError, OverflowError):
        return None


def parse_cell(col: str, typ: str, raw, existing):
    """→ (nilai, Issue|None). existing = nilai lama di DB (untuk saran pulihkan)."""
    if raw is None:
        return None, None
    if raw == TOO_LARGE:
        return KEEP_MARK, None
    label = col
    if typ == "json":
        if not isinstance(raw, str):
            return raw, None
        try:
            return json.loads(raw), None
        except json.JSONDecodeError as e:
            try:
                fixed = json.dumps(ast.literal_eval(raw), ensure_ascii=False)
                return raw, Issue(col, "error", f"{label}: JSON tidak sah ({e.msg}).", fixed)
            except (ValueError, SyntaxError):
                return raw, Issue(col, "error", f"{label}: JSON tidak sah ({e.msg}).")
    if typ in ("int", "float"):
        if isinstance(raw, bool):
            return raw, Issue(col, "error", f"{label}: TRUE/FALSE pada kolom angka.")
        if isinstance(raw, (int, float)):
            if typ == "int" and isinstance(raw, float) and not raw.is_integer():
                return raw, Issue(col, "warning", f"{label}: pecahan pada kolom bilangan bulat.",
                                  int(round(raw)))
            return raw, None
        n = _num_str(str(raw))
        if n is None:
            return raw, Issue(col, "error", f"{label}: '{raw}' bukan angka.")
        return raw, Issue(col, "error", f"{label}: angka ditulis sebagai teks.", n)
    if typ == "bool":
        if isinstance(raw, bool):
            return raw, None
        s = str(raw).strip().lower()
        if s in ("true", "false"):
            return s == "true", None
        if s in _TRUE or s in _FALSE:
            return s in _TRUE, Issue(col, "info", f"{label}: '{raw}' dibaca sebagai "
                                     f"{'TRUE' if s in _TRUE else 'FALSE'}.",
                                     "TRUE" if s in _TRUE else "FALSE")
        return raw, Issue(col, "error", f"{label}: '{raw}' harus TRUE/FALSE.")
    if typ == "datetime":
        s = str(raw)
        if _ISO_RE.match(s):
            return s, None
        d = _try_date(s)
        if d:
            return s, Issue(col, "error", f"{label}: tanggal bukan format ISO.", d.isoformat())
        return s, Issue(col, "error", f"{label}: '{raw}' bukan tanggal.")
    # str / any
    if isinstance(raw, bool):
        return ("TRUE" if raw else "FALSE"), None
    if isinstance(raw, (int, float)) and typ == "str":
        s = str(int(raw)) if isinstance(raw, float) and raw.is_integer() else str(raw)
        if isinstance(existing, str) and _num_str(existing) == raw and existing != s:
            return s, Issue(col, "warning", f"{label}: Excel mengubah teks menjadi angka.", existing)
        return s, Issue(col, "info", f"{label}: angka pada kolom teks — disimpan sebagai '{s}'.")
    if isinstance(raw, str) and typ == "any" and raw[:1] in "[{":
        try:
            return json.loads(raw), None
        except json.JSONDecodeError:
            pass
    if isinstance(raw, str) and typ == "str" and DATE_COL_RE.search(col) and not _ISO_RE.match(raw):
        d = _try_date(raw)
        if d and re.search(r"\d", raw):
            return raw, Issue(col, "warning", f"{label}: tanggal bukan format ISO.", d.date().isoformat())
    return raw, None


def column_issue(col: str, val, ctx: dict):
    """Aturan per kolom untuk nilai teks: org, telepon, email, rujukan, pilihan."""
    if not isinstance(val, str) or not val:
        return None
    if col == "org_id" and val != ctx["org"]:
        return Issue(col, "error", f"org_id '{val}' bukan organisasi ini.", ctx["org"])
    if _PHONE_COL.search(col):
        n = normalize_phone_e164(val)
        if n != val:
            return Issue(col, "info", "Nomor belum format +62.", n)
    if _EMAIL_COL.search(col):
        if not _EMAIL_RE.match(val):
            return Issue(col, "warning", f"'{val}' bukan email yang sah.")
        if val != val.lower():
            return Issue(col, "info", "Email memakai huruf besar.", val.lower())
    ref = REF_MAP.get(col)
    if ref and ref in ctx["ref_ids"] and val not in ctx["ref_ids"][ref]:
        return Issue(col, "warning", f"Rujukan {col} '{val}' tidak ditemukan di {ref}.")
    known = ctx["enum_values"].get(col)
    if known and val not in known:
        close = difflib.get_close_matches(val, list(known), n=1, cutoff=0.6)
        return Issue(col, "warning", f"Nilai '{val}' belum pernah dipakai pada kolom {col}.",
                     close[0] if close else None)
    return None


def _norm(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def same(a, b) -> bool:
    return json.dumps(_norm(a), sort_keys=True, default=str) == json.dumps(_norm(b), sort_keys=True, default=str)


def row_key(cells: dict):
    if cells.get("id") not in (None, ""):
        return "id", str(cells["id"])
    if cells.get("_id") not in (None, ""):
        return "_id", str(cells["_id"])
    return None, None


def _oid(key: str):
    try:
        return ObjectId(key)
    except (InvalidId, TypeError):
        return key


def key_query(kind: str, key: str, coll: str, org: str):
    if kind == "id":
        return {"id": key, **org_filter(coll, org)}
    return {"_id": {"$in": [_oid(key), key]}}


# ------------------------------------------------------------------ konteks DB
async def _ref_ids(colls: set, org: str, file_ids: dict) -> dict:
    out = {}
    for c in colls:
        ids = {d["id"] async for d in db[c].find(org_filter(c, org), {"_id": 0, "id": 1}) if d.get("id")}
        out[c] = ids | file_ids.get(c, set())
    return out


async def _enum_values(coll: str, cols: list, org: str) -> dict:
    out = {}
    n = await db[coll].count_documents(org_filter(coll, org))
    if n < 3:
        return out
    for c in cols:
        if not ENUM_COL_RE.search(c) or c in ("id", "_id"):
            continue
        vals = await db[coll].distinct(c, org_filter(coll, org))
        vals = {v for v in vals if isinstance(v, str)}
        if 0 < len(vals) <= 40:
            out[c] = vals
    return out


async def _existing(coll: str, sheet_rows: list, org: str) -> dict:
    ids = [k for _, k in (row_key(r["cells"]) for r in sheet_rows) if k]
    out = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        oids = [_oid(k) for k in chunk] + chunk
        q = {"$or": [{"id": {"$in": chunk}, **org_filter(coll, org)}, {"_id": {"$in": oids}}]}
        async for d in db[coll].find(q):
            out[str(d.get("id") or d["_id"])] = d
    return out


async def validate_sheet(sheet: dict, org: str, known_colls: set, file_ids: dict) -> dict:
    coll, rows, cols = sheet["collection"], sheet["rows"], sheet["columns"]
    known = coll in known_colls
    db_types = await sample_types(coll, org) if known else {}
    types = dict(db_types)
    types.update({c: t for c, t in (sheet.get("types") or {}).items() if t and t != "null"})
    for c in cols:
        types.setdefault(c, "any")
    new_cols = [c for c in cols if known and c not in db_types and c not in ("id", "_id")]
    refs = {REF_MAP[c] for c in cols if c in REF_MAP} & known_colls
    ctx = {"org": org, "ref_ids": await _ref_ids(refs, org, file_ids),
           "enum_values": await _enum_values(coll, cols, org) if known else {}}
    existing = await _existing(coll, rows, org) if known else {}
    seen, out_rows = {}, []
    counts = {"insert": 0, "update": 0, "same": 0, "error": 0, "warning": 0, "info": 0, "suggestion": 0}
    sheet_issues = []
    if not known:
        sheet_issues.append({"level": "error", "message": f"Koleksi '{coll}' tidak dikenal — "
                             "periksa nama sheet / sheet _INDEX."})
    if new_cols:
        sheet_issues.append({"level": "warning", "message": "Kolom baru (belum ada di DB): "
                             + ", ".join(new_cols)})
    for r in rows:
        cells, issues, values = r["cells"], [], {}
        kind, key = row_key(cells)
        doc = existing.get(key) if key else None
        for c in cols:
            if c in ("id", "_id"):
                values[c] = cells.get(c)
                continue
            val, iss = parse_cell(c, types.get(c, "any"), cells.get(c), (doc or {}).get(c))
            values[c] = val
            if iss:
                issues.append(iss)
            elif val is not None and val is not KEEP_MARK:
                ci = column_issue(c, val, ctx)
                if ci:
                    issues.append(ci)
        if key and key in seen:
            issues.append(Issue(kind, "error", f"Kunci {key} ganda (baris {seen[key]} sudah memuatnya)."))
        elif key:
            seen[key] = r["row"]
        changed = []
        if not known:
            status = "error"
        elif doc:
            changed = [c for c in cols if c not in ("id", "_id") and values[c] is not KEEP_MARK
                       and not same(values[c], doc.get(c))]
            status = "update" if changed else "same"
        else:
            status = "insert"
            if key:
                issues.append(Issue(kind, "info", f"Kunci {key} tidak ada di DB — akan dibuat sebagai data baru."))
            else:
                issues.append(Issue("id", "info", "id kosong — akan dibuat baru dengan id otomatis."))
        if any(i.level == "error" for i in issues):
            status = "error"
        counts[status] += 1
        for i in issues:
            if i.level != "error":
                counts[i.level] += 1
            if i.suggestion is not None:
                counts["suggestion"] += 1
        out_rows.append({"row": r["row"], "key": key, "cells": cells, "status": status,
                         "changed": changed, "issues": [i.out() for i in issues]})
    missing = []
    if known:
        keys = set(seen)
        async for d in db[coll].find(org_filter(coll, org), {"_id": 1, "id": 1, "name": 1, "code": 1}):
            k = str(d.get("id") or d["_id"])
            if k not in keys:
                missing.append({"key": k, "label": d.get("name") or d.get("code")})
    return {"sheet": sheet["sheet"], "collection": coll, "known": known, "columns": cols,
            "types": types, "total": len(rows), "counts": counts, "issues": sheet_issues,
            "missing_count": len(missing), "missing": missing[:100], "rows": out_rows,
            "values": None}


def parsed_values(report_row: dict, types: dict, cols: list) -> dict:
    """Ulang konversi sel → nilai siap tulis (dipakai commit; tanpa saran)."""
    out = {}
    for c in cols:
        if c in ("id", "_id"):
            continue
        val, _ = parse_cell(c, types.get(c, "any"), report_row["cells"].get(c), None)
        if val is KEEP_MARK:
            continue
        if isinstance(val, str) and types.get(c) in ("int", "float"):
            n = _num_str(val)
            val = n if n is not None else val
        out[c] = val
    return out


def guess_type(v) -> str:
    return type_of(v)
