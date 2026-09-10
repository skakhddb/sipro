import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Download, Layers } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { FULLDATA } from "@/constants/testIds";
import { downloadFile } from "../dataMgmtUtils";

const ORDER = ["transaksi", "proyek", "mitra", "konfigurasi", "lainnya"];

/** Pilih koleksi per kelompok lalu ekspor menjadi satu workbook (sheet per koleksi). */
export default function FullExportCard({ collections, groups, loading }) {
  const [excluded, setExcluded] = useState(new Set());
  const [open, setOpen] = useState({});
  const [busy, setBusy] = useState(false);

  const byGroup = useMemo(() => {
    const m = {};
    collections.forEach((c) => { (m[c.group] ||= []).push(c); });
    return m;
  }, [collections]);

  const selected = collections.filter((c) => !excluded.has(c.collection));
  const totalDocs = selected.reduce((s, c) => s + c.count, 0);

  const toggle = (names, on) => setExcluded((prev) => {
    const n = new Set(prev);
    names.forEach((x) => (on ? n.delete(x) : n.add(x)));
    return n;
  });

  const run = async (all) => {
    setBusy(true);
    const params = all ? undefined : { collections: selected.map((c) => c.collection).join(",") };
    await downloadFile("/data-mgmt/full/export.xlsx", "SIPRO_SemuaData.xlsx", params);
    setBusy(false);
  };

  return (
    <section data-testid={FULLDATA.exportCard} className="rounded-xl border bg-card p-5 space-y-4 shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Langkah 1</p>
          <h3 className="font-semibold">Ekspor semua data ke Excel</h3>
          <p className="text-sm text-muted-foreground">
            Setiap koleksi menjadi satu sheet lengkap dengan kolom <code>id</code>. Perbaiki di Excel,
            lalu unggah kembali — hanya sel yang berubah yang ditulis.
          </p>
        </div>
        <Layers className="h-8 w-8 text-primary shrink-0" />
      </div>

      <div className="rounded-lg border divide-y max-h-[420px] overflow-auto">
        {loading ? <p className="p-4 text-sm text-muted-foreground">Memuat…</p> : ORDER.filter((g) => byGroup[g]).map((g) => {
          const items = byGroup[g];
          const names = items.map((c) => c.collection);
          const on = names.filter((n) => !excluded.has(n)).length;
          const docs = items.filter((c) => !excluded.has(c.collection)).reduce((s, c) => s + c.count, 0);
          return (
            <div key={g} data-testid={`${FULLDATA.exportGroup}-${g}`}>
              <div className="flex items-center gap-3 px-3 py-2 bg-muted/40">
                <Checkbox data-testid={`${FULLDATA.exportGroupCheck}-${g}`}
                  checked={on === names.length ? true : on ? "indeterminate" : false}
                  onCheckedChange={(v) => toggle(names, v === true)} />
                <button type="button" className="flex flex-1 items-center gap-2 text-left text-sm font-medium"
                  onClick={() => setOpen((o) => ({ ...o, [g]: !o[g] }))}>
                  {open[g] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  {groups[g] || g}
                  <span className="text-xs text-muted-foreground font-normal">{on}/{names.length} koleksi · {docs.toLocaleString("id-ID")} dokumen</span>
                </button>
              </div>
              {open[g] ? (
                <ul className="grid sm:grid-cols-2 gap-x-4 px-3 py-2 text-xs">
                  {items.map((c) => (
                    <li key={c.collection} className="flex items-center gap-2 py-0.5">
                      <Checkbox data-testid={`${FULLDATA.exportCollection}-${c.collection}`} className="h-3.5 w-3.5"
                        checked={!excluded.has(c.collection)} onCheckedChange={(v) => toggle([c.collection], v === true)} />
                      <span className={cn("font-mono flex-1 truncate", excluded.has(c.collection) && "text-muted-foreground line-through")}>{c.collection}</span>
                      <span className="tabular-nums text-muted-foreground">{c.count}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button data-testid={FULLDATA.exportAll} disabled={busy || loading} onClick={() => run(true)}>
          <Download className="h-4 w-4 mr-2" /> {busy ? "Menyusun…" : "Ekspor semua koleksi"}
        </Button>
        <Button variant="outline" data-testid={FULLDATA.exportSelected}
          disabled={busy || loading || !selected.length || selected.length === collections.length}
          onClick={() => run(false)}>
          Ekspor {selected.length} koleksi terpilih
        </Button>
        <span className="text-xs text-muted-foreground ml-auto tabular-nums">{totalDocs.toLocaleString("id-ID")} dokumen dipilih</span>
      </div>
    </section>
  );
}
