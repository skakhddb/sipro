import React, { useEffect, useState } from "react";
import { CreditCard } from "lucide-react";
import { LoadingCards, ErrorState } from "@/components/patterns/StateViews";
import KprScheduleTable from "@/components/patterns/KprScheduleTable";
import { formatIDR, formatDateWIB } from "@/utils/formatters";
import portalApi from "@/services/portalClient";
import { PORTAL } from "@/constants/testIds";

export default function KprPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try {
      const res = await portalApi.get("/portal/kpr");
      setData(res.data.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat data KPR.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <LoadingCards count={2} />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data?.length) {
    return <p data-testid={PORTAL.kprEmpty} className="rounded-xl border bg-white p-6 text-center text-sm text-slate-500">Tidak ada unit dengan skema KPR pada akun Anda.</p>;
  }

  return (
    <div data-testid={PORTAL.kprPanel} className="space-y-6">
      {data.map((d) => (
        <div key={d.deal_id} data-testid={PORTAL.kprCard} className="space-y-4 rounded-xl border bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="flex items-center gap-1.5 text-xs text-slate-500"><CreditCard className="h-4 w-4" /> KPR unit {d.unit_code}</p>
              <p className="font-heading text-lg font-semibold">{d.bank_name || "Bank belum ditentukan"}{d.product_name ? ` · ${d.product_name}` : ""}</p>
              {d.stage_label ? <p className="text-xs text-slate-500">Tahap: {d.stage_label}</p> : null}
            </div>
            {d.available ? (
              <div className="text-right text-sm">
                <p className="text-xs text-slate-500">Plafon disetujui</p>
                <p className="font-semibold tabular-nums">{formatIDR(d.plafon)}</p>
                <p className="text-xs text-slate-500">{d.tenor_months} bulan · {d.interest_rate_pct}%/th{d.fixed_years ? ` fixed ${d.fixed_years} th` : ""}</p>
              </div>
            ) : null}
          </div>
          {d.available ? (
            <>
              {d.sp3k?.number || d.sp3k?.date ? (
                <p className="text-xs text-slate-500">SP3K {d.sp3k.number || ""}{d.sp3k.date ? ` · ${formatDateWIB(d.sp3k.date)}` : ""}{d.sp3k.valid_until ? ` · berlaku s.d. ${formatDateWIB(d.sp3k.valid_until)}` : ""}</p>
              ) : null}
              <KprScheduleTable data={d} rowTestId={PORTAL.kprScheduleRow} />
            </>
          ) : (
            <p data-testid={PORTAL.kprPending} className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{d.reason}</p>
          )}
        </div>
      ))}
    </div>
  );
}
