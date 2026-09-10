"""Manajemen Data — ekspor/impor SEMUA data (mentah per koleksi) dengan sesi viewer di server."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from rbac import audit_log
from routers.data_mgmt_router import require_data_admin, _org, _read_upload, XLSX
from data_mgmt_full_schema import list_collections, GROUP_LABELS
from data_mgmt_full_export import build_full_workbook
import data_mgmt_full_session as ses

router = APIRouter(prefix="/data-mgmt/full", tags=["data-mgmt"])


@router.get("/collections")
async def collections(user: dict = Depends(require_data_admin)):
    return {"collections": await list_collections(_org(user)), "groups": GROUP_LABELS,
            "sessions": await ses.list_sessions(_org(user))}


@router.get("/export.xlsx")
async def export_all(collections: str = "", user: dict = Depends(require_data_admin)):
    org = _org(user)
    available = {c["collection"] for c in await list_collections(org)}
    wanted = [c.strip() for c in collections.split(",") if c.strip()] or sorted(available)
    bad = [c for c in wanted if c not in available]
    if bad:
        raise HTTPException(status_code=400, detail=f"Koleksi tidak dikenal: {', '.join(bad)}")
    content, index = await build_full_workbook(org, wanted)
    await audit_log(user, "export_all", "data_mgmt", meta={"collections": len(index),
                                                            "documents": sum(r["count"] for r in index)})
    fname = f"SIPRO_SemuaData_{org}.xlsx"
    return Response(content=content, media_type=XLSX, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


@router.post("/sessions")
async def create_session(file: UploadFile = File(...), user: dict = Depends(require_data_admin)):
    content = await _read_upload(file, (".xlsx", ".xlsm"))
    try:
        rec = await ses.create_session(content, _org(user), user.get("email"), file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001 — openpyxl melempar banyak jenis galat untuk berkas rusak
        raise HTTPException(status_code=400, detail=f"Berkas Excel tidak bisa dibaca: {e}")
    return rec


def _lookup(fn):
    async def run(*a, **kw):
        try:
            return await fn(*a, **kw)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return run


@router.get("/sessions/{sid}")
async def session_report(sid: str, user: dict = Depends(require_data_admin)):
    rep = await _lookup(ses.report)(_org(user), sid)
    return {**rep, "sheets": [{k: v for k, v in s.items() if k != "rows"} for s in rep["sheets"]]}


@router.get("/sessions/{sid}/report.xlsx")
async def session_report_xlsx(sid: str, user: dict = Depends(require_data_admin)):
    content = await _lookup(ses.report_xlsx)(_org(user), sid)
    fname = f"SIPRO_LaporanValidasi_{sid[:8]}.xlsx"
    return Response(content=content, media_type=XLSX, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


@router.get("/sessions/{sid}/sheets/{sheet}")
async def session_sheet(sid: str, sheet: str, offset: int = 0, limit: int = 100,
                        only_issues: bool = False, status: str = None,
                        user: dict = Depends(require_data_admin)):
    rep = await _lookup(ses.report)(_org(user), sid)
    try:
        return ses.sheet_page(rep, sheet, offset, min(limit, 500), only_issues, status)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


class Edit(BaseModel):
    sheet: str
    row: int
    col: str
    value: object = None


class EditsRequest(BaseModel):
    edits: list[Edit]


@router.patch("/sessions/{sid}/cells")
async def edit_cells(sid: str, body: EditsRequest, user: dict = Depends(require_data_admin)):
    return await _lookup(ses.apply_edits)(_org(user), sid, [e.model_dump() for e in body.edits])


class DeleteRows(BaseModel):
    sheet: str
    rows: list[int]


@router.post("/sessions/{sid}/delete-rows")
async def remove_rows(sid: str, body: DeleteRows, user: dict = Depends(require_data_admin)):
    return await _lookup(ses.delete_rows)(_org(user), sid, body.sheet, body.rows)


class CommitRequest(BaseModel):
    mode: str = "update"
    sheets: list[str] = []
    skip_errors: bool = False
    confirm: str = ""


@router.post("/sessions/{sid}/commit")
async def commit_session(sid: str, body: CommitRequest, user: dict = Depends(require_data_admin)):
    if body.confirm.strip().upper() != "IMPOR":
        raise HTTPException(status_code=400, detail="Ketik IMPOR untuk mengonfirmasi.")
    try:
        res = await ses.commit(_org(user), sid, user.get("email"), body.mode, body.sheets,
                               body.skip_errors, user)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log(user, "import_all", "data_mgmt", entity_id=sid,
                    meta={"mode": body.mode, "totals": res["totals"]})
    return res


@router.delete("/sessions/{sid}")
async def drop_session(sid: str, user: dict = Depends(require_data_admin)):
    await ses.delete_session(_org(user), sid)
    return {"deleted": True}
