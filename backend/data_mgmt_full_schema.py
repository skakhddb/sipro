"""Katalog koleksi & tipe kolom untuk ekspor/impor SEMUA data (mode mentah per koleksi).

Setiap koleksi Mongo = satu sheet. Baris 1 = nama field, baris 2 = tipe (str/int/float/bool/
datetime/json), baris 3.. = dokumen. Field bertingkat (dict/list) ditulis sebagai JSON satu sel.
"""
import json
import re
from datetime import datetime

from bson import ObjectId

from db import db
from data_mgmt_purge import GROUPS, KEEP

EXCLUDED = {"file_blobs", "data_backups", "data_import_sessions", "portal_otps", "wa_webhook_events"}
NO_ORG = {"orgs", "permission_settings"}
TOO_LARGE = "«TERLALU BESAR — tidak diubah»"
KEEP_MARK = {"$keep": True}
CELL_MAX = 32000
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?([+-]\d{2}:?\d{2}|Z)?$")

GROUP_LABELS = {"transaksi": "Transaksi & operasional", "proyek": "Proyek, unit & konstruksi",
                "mitra": "Mitra, vendor & rekening", "konfigurasi": "Konfigurasi & master",
                "lainnya": "Lainnya"}
GROUP_OF = {c: g for g, spec in GROUPS.items() for c in spec["collections"]}
GROUP_OF.update({c: "konfigurasi" for c in KEEP})

# field *_id → koleksi rujukan (dipakai validasi rujukan silang)
REF_MAP = {
    "project_id": "projects", "cluster_id": "clusters", "block_id": "blocks", "unit_id": "units",
    "unit_type_id": "unit_types", "deal_id": "deals", "lead_id": "leads",
    "customer_id": "customers", "contract_id": "contracts", "agent_id": "agents",
    "partner_id": "agents", "vendor_id": "vendors", "subcon_id": "subcontractors",
    "subcontractor_id": "subcontractors", "spk_id": "spk", "user_id": "users",
    "invoice_id": "ar_invoices", "ar_invoice_id": "ar_invoices", "ap_invoice_id": "ap_invoices",
    "po_id": "purchase_orders", "purchase_order_id": "purchase_orders",
    "campaign_id": "campaigns", "scheme_id": "payment_schemes",
    "payment_scheme_id": "payment_schemes", "bank_account_id": "bank_accounts",
    "receipt_id": "receipts", "journal_id": "journal_entries", "task_id": "tasks",
    "complaint_id": "complaints", "permit_id": "permits", "schedule_id": "build_schedules",
    "material_id": "materials", "worker_id": "workers", "boq_item_id": "boq_items",
    "quotation_id": "quotations", "document_id": "documents", "loan_id": "loans",
    "asset_id": "fixed_assets", "inspection_id": "inspections", "promo_id": "promos",
    "coupon_id": "coupons", "conversation_id": "conversations", "addon_id": "addon_items",
}
ENUM_COL_RE = re.compile(r"(^|_)(status|type|kind|category|role|stage|source|method|channel|"
                         r"mode|level|priority|uom|treatment|basis|funding)$")
DATE_COL_RE = re.compile(r"(_at|_date|^date|_on|deadline|due)$")


def org_filter(coll: str, org: str) -> dict:
    if coll == "orgs":
        return {"id": org}
    if coll == "permission_settings":
        return {}
    return {"org_id": org}


def group_of(coll: str) -> str:
    return GROUP_OF.get(coll, "lainnya")


async def list_collections(org: str) -> list:
    names = sorted(n for n in await db.list_collection_names()
                   if not n.startswith("system.") and n not in EXCLUDED)
    out = []
    for n in names:
        cnt = await db[n].count_documents(org_filter(n, org))
        out.append({"collection": n, "count": cnt, "group": group_of(n),
                    "group_label": GROUP_LABELS[group_of(n)]})
    return out


# ------------------------------------------------------------------ tipe & serialisasi
def type_of(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, (dict, list)):
        return "json"
    if isinstance(v, datetime):
        return "datetime"
    if isinstance(v, str) and _ISO.match(v):
        return "datetime"
    return "str"


def dominant_type(types: list) -> str:
    ts = [t for t in types if t != "null"]
    if not ts:
        return "str"
    if set(ts) <= {"int", "float"}:
        return "float" if "float" in ts else "int"
    if set(ts) <= {"str", "datetime"}:
        return "datetime" if ts.count("datetime") > len(ts) * 0.8 else "str"
    if len(set(ts)) == 1:
        return ts[0]
    return "any"


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, ObjectId):
        return str(o)
    if isinstance(o, bytes):
        return "<bytes>"
    return str(o)


def to_cell(v):
    """Nilai dokumen → nilai sel Excel."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False, default=_json_default)
    elif isinstance(v, datetime):
        s = v.isoformat()
    elif isinstance(v, ObjectId):
        s = str(v)
    else:
        s = _ILLEGAL.sub("", str(v))
    if len(s) > CELL_MAX:
        return TOO_LARGE
    return s


def columns_for(docs: list) -> tuple:
    """(kolom terurut, tipe per kolom) dari kumpulan dokumen: id/org_id dulu, lalu urutan muncul."""
    order, types = [], {}
    for d in docs:
        for k, v in d.items():
            if k not in types:
                order.append(k)
                types[k] = []
            types[k].append(type_of(v))
    first = [c for c in ("id", "org_id", "code", "name") if c in types]
    rest = [c for c in order if c not in first]
    cols = first + rest
    return cols, {c: dominant_type(types[c]) for c in cols}


async def sample_types(coll: str, org: str, limit: int = 400) -> dict:
    docs = await db[coll].find(org_filter(coll, org), {"_id": 0}).limit(limit).to_list(limit)
    return columns_for(docs)[1]
