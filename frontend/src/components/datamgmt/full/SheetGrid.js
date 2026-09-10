import React, { useState } from "react";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { FULLDATA } from "@/constants/testIds";
import { LEVEL, STATUS, cellText, parseInput, topLevel } from "./fullImportUtils";

/** Grid spreadsheet: sel bermasalah disorot, sel berubah bergaris hijau, klik sel untuk edit/saran. */
export default function SheetGrid({ page, sheet, busy, onEdit, onDeleteRows }) {
  if (!page) return <div className="rounded-xl border bg-card p-8 text-sm text-muted-foreground">Memuat sheet…</div>;
  const cols = page.columns;
  return (
    <div className="rounded-xl border bg-card overflow-auto max-h-[70vh] shadow-[var(--shadow-card)]">
      <table data-testid={FULLDATA.grid} className="text-xs border-collapse min-w-full">
        <thead className="sticky top-0 z-10 bg-slate-800 text-slate-100">
          <tr>
            <th className="px-2 py-1.5 text-left font-medium sticky left-0 bg-slate-800 w-16">#</th>
            <th className="px-2 py-1.5 text-left font-medium whitespace-nowrap">Status</th>
            {cols.map((c) => (
              <th key={c} className="px-2 py-1.5 text-left font-mono font-medium whitespace-nowrap">
                {c}<span className="ml-1 text-[10px] text-slate-400 font-sans">{page.types[c]}</span>
              </th>
            ))}
            <th className="px-2 py-1.5" />
          </tr>
        </thead>
        <tbody>
          {page.rows.map((r) => (
            <GridRow key={r.row} row={r} cols={cols} sheet={sheet} busy={busy} onEdit={onEdit} onDelete={() => onDeleteRows([r.row])} />
          ))}
          {!page.rows.length ? <tr><td colSpan={cols.length + 3} className="px-4 py-6 text-center text-muted-foreground">Tidak ada baris untuk filter ini.</td></tr> : null}
        </tbody>
      </table>
    </div>
  );
}

function GridRow({ row, cols, sheet, busy, onEdit, onDelete }) {
  const S = STATUS[row.status] || STATUS.error;
  const byCol = {};
  row.issues.forEach((i) => { (byCol[i.col] ||= []).push(i); });
  return (
    <tr data-testid={`${FULLDATA.gridRow}-${row.row}`} className="border-t hover:bg-accent/30">
      <td className="px-2 py-1 tabular-nums text-muted-foreground sticky left-0 bg-card">{row.row}</td>
      <td className="px-2 py-1 whitespace-nowrap"><span className={cn("rounded border px-1.5 py-0.5 text-[10px]", S.cls)}>{S.label}</span></td>
      {cols.map((c) => (
        <Cell key={c} col={c} value={row.cells[c]} issues={byCol[c] || []} changed={row.changed.includes(c)}
          rowNo={row.row} sheet={sheet} busy={busy} onEdit={onEdit} />
      ))}
      <td className="px-1 py-1">
        <button type="button" data-testid={`${FULLDATA.deleteRow}-${row.row}`} title="Buang baris dari sesi"
          className="text-muted-foreground hover:text-destructive" disabled={busy} onClick={onDelete}>
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </td>
    </tr>
  );
}

function Cell({ col, value, issues, changed, rowNo, sheet, busy, onEdit }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const lvl = topLevel(issues);
  const txt = cellText(value);
  const suggestion = issues.find((i) => i.suggestion !== undefined);
  const save = () => { onEdit({ sheet, row: rowNo, col, value: parseInput(text) }); setOpen(false); };
  return (
    <td className="p-0">
      <Popover open={open} onOpenChange={(o) => { setOpen(o); if (o) setText(txt); }}>
        <PopoverTrigger asChild>
          <button type="button" data-testid={`${FULLDATA.gridCell}-${rowNo}-${col}`}
            data-level={lvl || undefined} data-changed={changed || undefined}
            className={cn("block w-full max-w-[260px] truncate px-2 py-1 text-left font-mono",
              lvl ? LEVEL[lvl].cell : "", changed && !lvl && "bg-emerald-50 ring-1 ring-inset ring-emerald-300",
              !txt && "text-muted-foreground/50")}>
            {txt || "∅"}
          </button>
        </PopoverTrigger>
        <PopoverContent data-testid={FULLDATA.cellPopover} align="start" className="w-80 space-y-2 text-xs">
          <p className="font-mono text-[11px] text-muted-foreground">baris {rowNo} · {col}{changed ? " · berubah dari DB" : ""}</p>
          {issues.map((i, k) => (
            <p key={k} className={cn("rounded border px-2 py-1", LEVEL[i.level].chip)}>{i.message}</p>
          ))}
          {suggestion ? (
            <Button size="sm" variant="secondary" className="w-full h-7" data-testid={FULLDATA.cellApply} disabled={busy}
              onClick={() => { onEdit({ sheet, row: rowNo, col, value: suggestion.suggestion }); setOpen(false); }}>
              Terapkan saran: <span className="font-mono ml-1 truncate">{cellText(suggestion.suggestion)}</span>
            </Button>
          ) : null}
          <textarea data-testid={FULLDATA.cellInput} value={text} onChange={(e) => setText(e.target.value)} rows={txt.length > 60 ? 5 : 2}
            className="w-full rounded border bg-background p-1.5 font-mono text-xs"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); save(); } }} />
          <div className="flex gap-1">
            <Button size="sm" className="h-7 flex-1" data-testid={FULLDATA.cellSave} disabled={busy} onClick={save}>Simpan sel</Button>
            <Button size="sm" variant="ghost" className="h-7" onClick={() => setOpen(false)}>Batal</Button>
          </div>
        </PopoverContent>
      </Popover>
    </td>
  );
}
