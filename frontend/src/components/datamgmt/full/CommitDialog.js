import React, { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FULLDATA } from "@/constants/testIds";
import { errDetail } from "../dataMgmtUtils";
import { sessionApi } from "./fullImportUtils";

/** Konfirmasi impor: mode update/replace, pilih sheet, lewati error, ketik IMPOR. */
export default function CommitDialog({ open, onOpenChange, sessionId, report, onDone }) {
  const [mode, setMode] = useState("update");
  const [skipErrors, setSkipErrors] = useState(false);
  const [excluded, setExcluded] = useState(new Set());
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const usable = report.sheets.filter((s) => s.known);
  const chosen = usable.filter((s) => !excluded.has(s.sheet));
  const errors = chosen.reduce((n, s) => n + s.counts.error, 0);
  const missing = chosen.reduce((n, s) => n + s.missing_count, 0);
  const writes = chosen.reduce((n, s) => n + s.counts.insert + s.counts.update, 0);

  const submit = async () => {
    setBusy(true);
    try {
      const res = await sessionApi.commit(sessionId, { mode, sheets: chosen.map((s) => s.sheet), skip_errors: skipErrors, confirm });
      toast.success(`Impor selesai: ${res.totals.inserted} baru, ${res.totals.updated} diperbarui, ${res.totals.deleted} dihapus.`);
      onDone?.(res); onOpenChange(false); setConfirm("");
    } catch (e) { toast.error(errDetail(e, "Impor gagal.")); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={FULLDATA.commitDialog} className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Jalankan impor semua data</DialogTitle>
          <DialogDescription>Snapshot pengaman dibuat otomatis sebelum menulis. {writes} baris akan ditulis pada {chosen.length} sheet.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Perilaku terhadap data di sistem</p>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger data-testid={FULLDATA.commitMode}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="update">Update — tulis baris di Excel saja, data lain dibiarkan (aman)</SelectItem>
                <SelectItem value="replace">Replace — baris yang tidak ada di Excel DIHAPUS dari sistem</SelectItem>
              </SelectContent>
            </Select>
            {mode === "replace" ? (
              <p className="flex items-start gap-1.5 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800">
                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" /> {missing} dokumen di DB tidak ada di sheet terpilih dan akan dihapus. Akun super admin & akun Anda tidak pernah dihapus.
              </p>
            ) : null}
          </div>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Sheet yang diimpor</p>
            <ul className="max-h-40 overflow-auto rounded border divide-y text-xs">
              {usable.map((s) => (
                <li key={s.sheet} className="flex items-center gap-2 px-2 py-1">
                  <Checkbox className="h-3.5 w-3.5" checked={!excluded.has(s.sheet)}
                    onCheckedChange={(v) => setExcluded((p) => { const n = new Set(p); v ? n.delete(s.sheet) : n.add(s.sheet); return n; })} />
                  <span className="font-mono flex-1">{s.sheet}</span>
                  <span className="text-emerald-700">+{s.counts.insert}</span>
                  <span className="text-sky-700">~{s.counts.update}</span>
                  {s.counts.error ? <span className="text-rose-700">!{s.counts.error}</span> : null}
                </li>
              ))}
            </ul>
          </div>
          {report.checks?.length ? (
            <p data-testid={FULLDATA.commitChecksWarning} className="flex items-start gap-1.5 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" /> {report.checks.length} peringatan konsistensi silang (Σ termin AR ≠ harga deal/kontrak, dll.) belum diselesaikan. Impor tetap bisa dijalankan, tetapi angka piutang akan tidak sinkron.
            </p>
          ) : null}
          {errors ? (
            <label className="flex items-center gap-2 text-xs">
              <Checkbox data-testid={FULLDATA.commitSkipErrors} checked={skipErrors} onCheckedChange={(v) => setSkipErrors(v === true)} />
              Lewati {errors} baris error (baris lain tetap diimpor)
            </label>
          ) : null}
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Ketik <b>IMPOR</b> untuk mengonfirmasi</p>
            <Input data-testid={FULLDATA.commitConfirm} value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="IMPOR" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Batal</Button>
          <Button data-testid={FULLDATA.commitSubmit} variant={mode === "replace" ? "destructive" : "default"}
            disabled={busy || confirm.trim().toUpperCase() !== "IMPOR" || !chosen.length || (errors > 0 && !skipErrors)} onClick={submit}>
            {busy ? "Mengimpor…" : mode === "replace" ? "Replace data" : "Jalankan impor"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
