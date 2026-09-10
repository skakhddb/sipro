import React, { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Scale } from "lucide-react";

import { cn } from "@/lib/utils";
import { FULLDATA } from "@/constants/testIds";

/** Cek konsistensi silang (AR vs harga deal/kontrak) — hasil setelah baris sheet diterapkan. */
export default function CrossChecksPanel({ checks, onJump }) {
  const [open, setOpen] = useState(true);
  if (!checks?.length) return null;
  return (
    <div data-testid={FULLDATA.checksPanel} className="rounded-xl border border-amber-200 bg-amber-50/60 shadow-[var(--shadow-card)]">
      <button type="button" data-testid={FULLDATA.checksToggle} onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-semibold text-amber-900">
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Scale className="h-4 w-4" /> Konsistensi silang: {checks.length} peringatan
        <span className="ml-auto text-xs font-normal text-amber-800">Σ termin AR vs harga deal/kontrak, total, paid & outstanding</span>
      </button>
      {open ? (
        <ul className="divide-y divide-amber-200 border-t border-amber-200 text-xs max-h-56 overflow-auto">
          {checks.map((c, k) => (
            <li key={k} data-testid={`${FULLDATA.checkItem}-${c.code}-${c.key}`} className="flex items-start gap-2 px-4 py-2 text-amber-900">
              <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <p><b>{c.label || c.collection}</b> · {c.message}</p>
                <p className="font-mono text-[11px] text-amber-800/80">
                  {c.code} · {c.sheet ? `sheet ${c.sheet} baris ${c.row}` : `dokumen di DB (${c.collection}), tidak ada di berkas`} · {c.key}
                </p>
              </div>
              {c.sheet ? (
                <button type="button" className={cn("shrink-0 rounded border border-amber-300 px-2 py-0.5 hover:bg-amber-100")}
                  onClick={() => onJump?.(c.sheet, c.row)}>Lihat baris</button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
