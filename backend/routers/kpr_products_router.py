"""Master Produk KPR per bank: tenor yang tersedia & suku bunga — sumber tunggal untuk form
pengajuan KPR (Customer & Kontrak) dan tahap SP3K (kontrak), menggantikan ketik bebas."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import db, ORG_ID
from core_utils import new_id, now_iso, serialize_doc
from rbac import require_permission, audit_log

router = APIRouter(prefix="/master/kpr-products", tags=["master-data"])
COLL = "kpr_products"


class KprProductIn(BaseModel):
    bank_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tenors: list[int] = Field(min_length=1)
    interest_rate_pct: float = Field(ge=0, le=100)
    fixed_years: int | None = Field(default=None, ge=0, le=40)
    floating_rate_pct: float | None = Field(default=None, ge=0, le=100)
    min_dp_pct: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    is_active: bool = True


def _clean(p: KprProductIn) -> dict:
    tenors = sorted({int(t) for t in p.tenors if 1 <= int(t) <= 480})
    if not tenors:
        raise HTTPException(status_code=400, detail="Isi minimal satu tenor (1–480 bulan).")
    d = p.model_dump()
    d.update({"bank_name": p.bank_name.strip(), "name": p.name.strip(), "tenors": tenors})
    return d


@router.get("")
async def list_products(bank_name: str = None, include_inactive: bool = False,
                        user: dict = Depends(require_permission("financing", "view"))):
    q = {"org_id": user.get("org_id", ORG_ID)}
    if bank_name:
        q["bank_name"] = bank_name
    if not include_inactive:
        q["is_active"] = True
    rows = await db[COLL].find(q, {"_id": 0}).sort([("bank_name", 1), ("name", 1)]).to_list(500)
    return {"data": serialize_doc(rows), "total": len(rows)}


@router.post("")
async def create_product(payload: KprProductIn,
                         user: dict = Depends(require_permission("settings", "manage"))):
    org = user.get("org_id", ORG_ID)
    data = _clean(payload)
    if await db[COLL].find_one({"org_id": org, "bank_name": data["bank_name"], "name": data["name"]}):
        raise HTTPException(status_code=409, detail=f"Produk '{data['name']}' untuk {data['bank_name']} sudah ada.")
    doc = {"id": new_id(), "org_id": org, **data, "created_by": user.get("email"),
           "created_at": now_iso(), "updated_at": now_iso()}
    await db[COLL].insert_one(dict(doc))
    await audit_log(user, "create", COLL, doc["id"], {"bank": data["bank_name"], "name": data["name"]})
    doc.pop("_id", None)
    return {"data": serialize_doc(doc)}


@router.put("/{pid}")
async def update_product(pid: str, payload: KprProductIn,
                         user: dict = Depends(require_permission("settings", "manage"))):
    org = user.get("org_id", ORG_ID)
    data = _clean(payload)
    dup = await db[COLL].find_one({"org_id": org, "bank_name": data["bank_name"], "name": data["name"],
                                   "id": {"$ne": pid}})
    if dup:
        raise HTTPException(status_code=409, detail=f"Produk '{data['name']}' untuk {data['bank_name']} sudah ada.")
    res = await db[COLL].update_one({"id": pid, "org_id": org}, {"$set": {**data, "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Produk KPR tidak ditemukan.")
    await audit_log(user, "update", COLL, pid, {"fields": sorted(data)})
    return {"data": serialize_doc(await db[COLL].find_one({"id": pid}, {"_id": 0}))}


@router.delete("/{pid}")
async def archive_product(pid: str, user: dict = Depends(require_permission("settings", "manage"))):
    """Arsip (nonaktif) — pengajuan yang sudah memakai produk ini tetap menyimpan angkanya."""
    org = user.get("org_id", ORG_ID)
    res = await db[COLL].update_one({"id": pid, "org_id": org},
                                    {"$set": {"is_active": False, "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Produk KPR tidak ditemukan.")
    await audit_log(user, "archive", COLL, pid)
    return {"data": {"id": pid, "is_active": False}}
