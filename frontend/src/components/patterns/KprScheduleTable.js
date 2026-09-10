import React from "react";
import { formatIDR } from "@/utils/formatters";

/**
 * Tabel angsuran per tahun dari `schedule_of` (backend) — dipakai portal pembeli & panel staf.
 * data: { rows[], fixed_installment, floating_installment, floating_rate_pct, total_interest, total_paid }
 */
export default function KprScheduleTable({ data, rowTestId, compact = false }) {
  if (!data?.rows?.length) return null;
  const cell = compact ? "px-2 py-1" : "px-3 py-1.5";
  return (
    <div className="space-y-2">
      <div className={`grid gap-2 text-xs ${data.floating_installment ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
        <div className="rounded-lg border bg-background p-2">
          <p className="text-muted-foreground">Angsuran{data.floating_installment ? ` masa fixed (${Math.round(data.fixed_months / 12)} th)` : ""}</p>
          <p className="font-semibold tabular-nums">{formatIDR(data.fixed_installment)}/bln</p>
        </div>
        {data.floating_installment ? (
          <div className="rounded-lg border bg-background p-2">
            <p className="text-muted-foreground">Setelah fixed (floating {data.floating_rate_pct}%)</p>
            <p className="font-semibold tabular-nums">±{formatIDR(data.floating_installment)}/bln</p>
          </div>
        ) : null}
        <div className="rounded-lg border bg-background p-2">
          <p className="text-muted-foreground">Total bunga · total bayar</p>
          <p className="font-semibold tabular-nums">{formatIDR(data.total_interest)} · {formatIDR(data.total_paid)}</p>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-xs">
          <thead className="bg-muted/50 text-left text-muted-foreground">
            <tr>
              <th className={cell}>Tahun</th><th className={cell}>Bunga</th><th className={cell}>Angsuran/bln</th>
              <th className={cell}>Pokok dibayar</th><th className={cell}>Bunga dibayar</th><th className={cell}>Sisa pokok</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.year} data-testid={rowTestId} data-phase={r.phase} className="border-t tabular-nums">
                <td className={cell}>Tahun {r.year}{r.months < 12 ? ` (${r.months} bln)` : ""}</td>
                <td className={cell}>{r.rate}% <span className="text-muted-foreground">{r.phase === "floating" ? "floating" : "fixed"}</span></td>
                <td className={`${cell} font-medium`}>{formatIDR(r.installment)}</td>
                <td className={cell}>{formatIDR(r.principal_paid)}</td>
                <td className={cell}>{formatIDR(r.interest_paid)}</td>
                <td className={cell}>{formatIDR(r.balance_end)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted-foreground">Simulasi anuitas dari plafon, tenor & bunga yang tercatat — angka pasti mengikuti jadwal resmi bank.</p>
    </div>
  );
}
