import React, { useState } from "react";
import { toast } from "sonner";
import { FileSpreadsheet, FolderOpen, Trash2, UploadCloud } from "lucide-react";

import api from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import { formatDateTimeWIB } from "@/utils/formatters";
import { FULLDATA } from "@/constants/testIds";
import { errDetail } from "../dataMgmtUtils";
import { sessionApi } from "./fullImportUtils";

/** Unggah workbook hasil ekspor → sesi impor; sesi sebelumnya bisa dibuka kembali. */
export default function FullImportUpload({ sessions, onSession, onChanged }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);

  const upload = async () => {
    if (!file) { toast.error("Pilih berkas Excel terlebih dahulu."); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const res = await api.post("/data-mgmt/full/sessions", fd);
      toast.success(`Berkas dibaca: ${res.data.sheets.length} sheet. Memvalidasi…`);
      onSession(res.data.id);
    } catch (e) { toast.error(errDetail(e, "Berkas tidak bisa dibaca.")); } finally { setBusy(false); }
  };

  const remove = async (sid) => {
    try { await sessionApi.remove(sid); onChanged?.(); } catch (e) { toast.error(errDetail(e, "Gagal menghapus sesi.")); }
  };

  return (
    <section className="space-y-4">
      <div className="rounded-xl border bg-card p-5 space-y-3 shadow-[var(--shadow-card)]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow">Langkah 2</p>
            <h3 className="font-semibold">Unggah hasil perbaikan</h3>
            <p className="text-sm text-muted-foreground">
              Berkas divalidasi per sel: error, peringatan, dan saran koreksi ditampilkan di viewer.
              Anda bisa menyunting sel langsung sebelum impor dijalankan.
            </p>
          </div>
          <FileSpreadsheet className="h-8 w-8 text-primary shrink-0" />
        </div>
        <label
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center hover:bg-accent/40 transition-colors"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); setFile(e.dataTransfer.files?.[0] || null); }}>
          <UploadCloud className="h-7 w-7 text-muted-foreground" />
          <span className="text-sm">{file ? <b>{file.name}</b> : "Seret berkas .xlsx ke sini atau klik untuk memilih"}</span>
          <input data-testid={FULLDATA.fileInput} type="file" accept=".xlsx,.xlsm" className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        <Button data-testid={FULLDATA.uploadBtn} disabled={!file || busy} onClick={upload}>
          <UploadCloud className="h-4 w-4 mr-2" /> {busy ? "Membaca berkas…" : "Unggah & buka viewer"}
        </Button>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden shadow-[var(--shadow-card)]">
        <div className="px-5 py-3 border-b"><h3 className="font-semibold text-sm">Sesi impor sebelumnya</h3></div>
        {!sessions?.length ? (
          <p className="px-5 py-4 text-sm text-muted-foreground">Belum ada sesi. Sesi tersimpan di server agar bisa dilanjutkan.</p>
        ) : (
          <ul className="divide-y text-sm">
            {sessions.map((s) => (
              <li key={s.id} data-testid={`${FULLDATA.sessionRow}-${s.id}`} className="flex items-center gap-3 px-5 py-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{s.filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDateTimeWIB(s.created_at)} · {s.sheets?.length} sheet · {s.created_by}
                    {s.status === "committed" ? <span className="ml-2 rounded bg-emerald-50 px-1.5 text-emerald-800">sudah diimpor ({s.mode})</span> : null}
                  </p>
                </div>
                <Button size="sm" variant="secondary" data-testid={`${FULLDATA.sessionOpen}-${s.id}`} onClick={() => onSession(s.id)}>
                  <FolderOpen className="h-3.5 w-3.5 mr-1" /> Buka
                </Button>
                <Button size="icon" variant="ghost" data-testid={`${FULLDATA.sessionDelete}-${s.id}`} onClick={() => remove(s.id)}>
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
