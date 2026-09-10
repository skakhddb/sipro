import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Download, PlayCircle, RefreshCw, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { FULLDATA } from "@/constants/testIds";
import { downloadFile, errDetail } from "../dataMgmtUtils";
import { sessionApi } from "./fullImportUtils";
import SheetGrid from "./SheetGrid";
import IssuePanel from "./IssuePanel";
import CommitDialog from "./CommitDialog";
import CrossChecksPanel from "./CrossChecksPanel";

const PAGE = 100;

/** Viewer sesi impor: ringkasan, tab sheet, grid sel + panel temuan, lalu commit. */
export default function ImportWorkbench({ sessionId, onClose, onCommitted }) {
  const [report, setReport] = useState(null);
  const [sheet, setSheet] = useState(null);
  const [page, setPage] = useState(null);
  const [filter, setFilter] = useState("all");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [commitOpen, setCommitOpen] = useState(false);
  const [result, setResult] = useState(null);

  const loadReport = useCallback(async () => {
    try {
      const rep = await sessionApi.report(sessionId);
      setReport(rep);
      setSheet((s) => s && rep.sheets.some((x) => x.sheet === s) ? s : rep.sheets[0]?.sheet || null);
    } catch (e) { toast.error(errDetail(e, "Sesi tidak bisa dimuat.")); onClose(); }
  }, [sessionId, onClose]);

  const loadPage = useCallback(async () => {
    if (!sheet) return;
    const params = { offset, limit: PAGE };
    if (filter === "issues") params.only_issues = true;
    else if (filter !== "all") params.status = filter;
    try { setPage(await sessionApi.sheet(sessionId, sheet, params)); }
    catch (e) { toast.error(errDetail(e, "Sheet tidak bisa dimuat.")); }
  }, [sessionId, sheet, filter, offset]);

  useEffect(() => { loadReport(); }, [loadReport]);
  useEffect(() => { loadPage(); }, [loadPage]);
  const jumpRef = React.useRef(null);
  useEffect(() => { setOffset(jumpRef.current ?? 0); jumpRef.current = null; }, [sheet, filter]);
  const jumpTo = (s, row) => {
    const off = Math.floor(Math.max(0, row - 3) / PAGE) * PAGE;
    jumpRef.current = off; setFilter("all"); setSheet(s); setOffset(off);
  };

  const refresh = async () => { setBusy(true); await loadReport(); await loadPage(); setBusy(false); };

  const applyEdits = async (edits) => {
    if (!edits.length) return;
    setBusy(true);
    try {
      await sessionApi.edit(sessionId, edits);
      toast.success(`${edits.length} sel diperbarui — validasi ulang…`);
      await loadReport(); await loadPage();
    } catch (e) { toast.error(errDetail(e, "Sel tidak bisa disimpan.")); } finally { setBusy(false); }
  };

  const deleteRows = async (rows) => {
    setBusy(true);
    try {
      await sessionApi.deleteRows(sessionId, sheet, rows);
      toast.success(`${rows.length} baris dibuang dari sesi.`);
      await loadReport(); await loadPage();
    } catch (e) { toast.error(errDetail(e, "Baris tidak bisa dibuang.")); } finally { setBusy(false); }
  };

  const applyAllSuggestions = async () => {
    try {
      const all = await sessionApi.sheet(sessionId, sheet, { only_issues: true, limit: 500 });
      const edits = [];
      all.rows.forEach((r) => r.issues.forEach((i) => {
        if (i.suggestion !== undefined && i.level !== "info") edits.push({ sheet, row: r.row, col: i.col, value: i.suggestion });
      }));
      if (!edits.length) { toast.info("Tidak ada saran error/peringatan di sheet ini."); return; }
      await applyEdits(edits);
    } catch (e) { toast.error(errDetail(e, "Gagal mengambil saran.")); }
  };

  const current = useMemo(() => report?.sheets.find((s) => s.sheet === sheet), [report, sheet]);
  const t = report?.totals;
  const pageCount = page ? Math.ceil(page.filtered / PAGE) : 0;

  if (!report) return <p className="text-sm text-muted-foreground p-6">Memvalidasi berkas…</p>;

  return (
    <div data-testid={FULLDATA.workbench} className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" data-testid={FULLDATA.closeWorkbench} onClick={onClose}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Kembali
        </Button>
        <div className="min-w-0">
          <p className="font-semibold truncate">{report.filename}</p>
          <p className="text-xs text-muted-foreground">{report.sheets.length} sheet · {t.rows.toLocaleString("id-ID")} baris</p>
        </div>
        <div data-testid={FULLDATA.totals} className="ml-auto flex flex-wrap gap-4 text-right">
          <Stat l="Baru" v={t.insert} c="text-emerald-700" />
          <Stat l="Diubah" v={t.update} c="text-sky-700" />
          <Stat l="Sama" v={t.same} />
          <Stat l="Error" v={t.error} c={t.error ? "text-rose-700" : ""} />
          <Stat l="Peringatan" v={t.warning} c={t.warning ? "text-amber-700" : ""} />
          <Stat l="Saran" v={t.suggestion} c={t.suggestion ? "text-violet-700" : ""} />
          <Stat l="Cek silang" v={t.checks || 0} c={t.checks ? "text-amber-700" : ""} />
        </div>
        <Button variant="outline" data-testid={FULLDATA.downloadReport} disabled={busy}
          onClick={() => downloadFile(`/data-mgmt/full/sessions/${sessionId}/report.xlsx`, "SIPRO_LaporanValidasi.xlsx")}>
          <Download className="h-4 w-4 mr-2" /> Laporan validasi (Excel)
        </Button>
        <Button data-testid={FULLDATA.commitOpen} disabled={busy} onClick={() => setCommitOpen(true)}>
          <PlayCircle className="h-4 w-4 mr-2" /> Jalankan impor…
        </Button>
      </div>

      {result ? <CommitResult result={result} /> : null}
      <CrossChecksPanel checks={report.checks} onJump={jumpTo} />

      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {report.sheets.map((s) => {
          const err = s.counts.error + (s.issues.some((i) => i.level === "error") ? 1 : 0);
          return (
            <button key={s.sheet} type="button" data-testid={`${FULLDATA.sheetTab}-${s.sheet}`}
              onClick={() => setSheet(s.sheet)}
              className={cn("shrink-0 rounded-full border px-3 py-1 text-xs font-mono transition-colors",
                s.sheet === sheet ? "bg-primary text-primary-foreground border-primary" : "bg-card hover:bg-accent/50")}>
              {s.sheet} <span className="opacity-70">{s.total}</span>
              {err ? <span className="ml-1.5 rounded-full bg-rose-500 px-1.5 text-[10px] text-white">{err}</span> : null}
              {!err && s.counts.warning ? <span className="ml-1.5 rounded-full bg-amber-400 px-1.5 text-[10px] text-black">{s.counts.warning}</span> : null}
            </button>
          );
        })}
      </div>

      {current?.issues.length ? (
        <div className="space-y-1">
          {current.issues.map((i, k) => (
            <p key={k} data-testid={`${FULLDATA.sheetIssue}-${i.level}`}
              className={cn("rounded border px-3 py-1.5 text-xs", i.level === "error" ? "bg-rose-50 text-rose-800 border-rose-200" : "bg-amber-50 text-amber-800 border-amber-200")}>
              {i.message}
            </p>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger data-testid={FULLDATA.filter} className="w-56 h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Semua baris</SelectItem>
            <SelectItem value="issues">Hanya baris bermasalah</SelectItem>
            <SelectItem value="error">Status: error</SelectItem>
            <SelectItem value="update">Status: diubah</SelectItem>
            <SelectItem value="insert">Status: baru</SelectItem>
            <SelectItem value="same">Status: sama</SelectItem>
          </SelectContent>
        </Select>
        <Button size="sm" variant="secondary" data-testid={FULLDATA.applyAllSuggestions} disabled={busy || !current?.counts.suggestion} onClick={applyAllSuggestions}>
          <Wand2 className="h-3.5 w-3.5 mr-1" /> Terapkan semua saran (sheet ini)
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={refresh}><RefreshCw className={cn("h-3.5 w-3.5", busy && "animate-spin")} /></Button>
        {current ? (
          <span className="ml-auto text-xs text-muted-foreground">
            {current.missing_count ? `${current.missing_count} dokumen di DB tidak ada di sheet (akan dihapus pada mode replace) · ` : ""}
            {page ? `${page.filtered} baris ditampilkan` : ""}
          </span>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <SheetGrid page={page} sheet={sheet} busy={busy} onEdit={(e) => applyEdits([e])} onDeleteRows={deleteRows} />
        <IssuePanel page={page} sheet={sheet} busy={busy} onApply={(e) => applyEdits([e])} />
      </div>

      {pageCount > 1 ? (
        <div data-testid={FULLDATA.pager} className="flex items-center justify-center gap-2 text-xs">
          <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Sebelumnya</Button>
          <span>Halaman {Math.floor(offset / PAGE) + 1} / {pageCount}</span>
          <Button size="sm" variant="outline" disabled={offset + PAGE >= page.filtered} onClick={() => setOffset(offset + PAGE)}>Berikutnya</Button>
        </div>
      ) : null}

      <CommitDialog open={commitOpen} onOpenChange={setCommitOpen} sessionId={sessionId} report={report}
        onDone={(res) => { setResult(res); onCommitted?.(); loadReport(); loadPage(); }} />
    </div>
  );
}

function Stat({ l, v, c }) {
  return <div><p className="text-[10px] uppercase text-muted-foreground">{l}</p><p className={cn("text-lg font-semibold tabular-nums leading-tight", c)}>{v}</p></div>;
}

function CommitResult({ result }) {
  const t = result.totals;
  return (
    <div data-testid={FULLDATA.commitResult} className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
      <p className="font-semibold">Impor selesai (mode {result.mode}) — {t.inserted} baru · {t.updated} diperbarui · {t.unchanged} sama · {t.deleted} dihapus · {t.skipped} dilewati.</p>
      <p className="text-xs mt-1">Snapshot pengaman: <code>{result.snapshot_before?.filename}</code> (tab Backup & Snapshot).</p>
      <p className="text-xs mt-1 font-mono">{Object.entries(result.collections).map(([c, r]) => `${c}: +${r.inserted} ~${r.updated} -${r.deleted}`).join(" · ")}</p>
    </div>
  );
}
