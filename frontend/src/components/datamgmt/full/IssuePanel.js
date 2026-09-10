import React from "react";
import { Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { FULLDATA } from "@/constants/testIds";
import { LEVEL, cellText } from "./fullImportUtils";

/** Daftar temuan pada halaman aktif, error dulu; tiap saran punya tombol terapkan. */
export default function IssuePanel({ page, sheet, busy, onApply }) {
  const items = [];
  (page?.rows || []).forEach((r) => r.issues.forEach((i) => items.push({ ...i, row: r.row })));
  const order = { error: 0, warning: 1, info: 2 };
  items.sort((a, b) => order[a.level] - order[b.level] || a.row - b.row);
  const counts = items.reduce((m, i) => ({ ...m, [i.level]: (m[i.level] || 0) + 1 }), {});

  return (
    <aside data-testid={FULLDATA.issueList} className="rounded-xl border bg-card overflow-hidden shadow-[var(--shadow-card)] max-h-[70vh] flex flex-col">
      <div className="px-4 py-2.5 border-b">
        <h4 className="font-semibold text-sm">Temuan halaman ini</h4>
        <p className="text-[11px] text-muted-foreground flex gap-2 mt-0.5">
          {["error", "warning", "info"].map((l) => (
            <span key={l} className="inline-flex items-center gap-1">
              <span className={cn("h-2 w-2 rounded-full", LEVEL[l].dot)} />{counts[l] || 0} {LEVEL[l].label.toLowerCase()}
            </span>
          ))}
        </p>
      </div>
      {!items.length ? (
        <p className="p-4 text-sm text-muted-foreground">Tidak ada temuan pada baris yang ditampilkan.</p>
      ) : (
        <ul className="divide-y overflow-auto text-xs">
          {items.map((i, k) => (
            <li key={k} data-testid={`${FULLDATA.issueItem}-${i.row}-${i.col}`} className="px-4 py-2 space-y-1">
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 rounded-full shrink-0", LEVEL[i.level].dot)} />
                <span className="font-mono text-[11px] text-muted-foreground">baris {i.row} · {i.col}</span>
              </div>
              <p>{i.message}</p>
              {i.suggestion !== undefined ? (
                <Button size="sm" variant="outline" className="h-6 text-[11px] w-full justify-start" disabled={busy}
                  data-testid={`${FULLDATA.issueApply}-${i.row}-${i.col}`}
                  onClick={() => onApply({ sheet, row: i.row, col: i.col, value: i.suggestion })}>
                  <Wand2 className="h-3 w-3 mr-1 shrink-0" /> <span className="truncate">→ {cellText(i.suggestion)}</span>
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
