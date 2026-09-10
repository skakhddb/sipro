import React, { useEffect, useMemo, useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatIDR } from "@/utils/formatters";
import api from "@/services/apiClient";

/** Angsuran anuitas per bulan: P·r / (1 − (1+r)^−n), r = bunga tahunan/12. */
export function monthlyInstallment(plafon, ratePct, tenorMonths) {
  const P = Number(plafon) || 0; const n = Number(tenorMonths) || 0; const r = (Number(ratePct) || 0) / 100 / 12;
  if (P <= 0 || n <= 0) return 0;
  if (r === 0) return Math.round(P / n);
  return Math.round((P * r) / (1 - Math.pow(1 + r, -n)));
}

function InstallmentHint({ plafon, rate, tenor, floating, fixedYears, testId }) {
  const m = monthlyInstallment(plafon, rate, tenor);
  if (!m) return null;
  const fl = floating != null && Number(floating) !== Number(rate) ? monthlyInstallment(plafon, floating, tenor) : 0;
  return (
    <p data-testid={testId} className="rounded-md border border-dashed bg-muted/40 px-2 py-1.5 text-xs sm:col-span-2">
      Estimasi angsuran <b>{formatIDR(m)}</b>/bulan{fixedYears ? ` (masa fixed ${fixedYears} th)` : ""}
      {fl ? <> · setelah fixed ±<b>{formatIDR(fl)}</b>/bulan (floating {floating}%)</> : null}
      <span className="text-muted-foreground"> — simulasi anuitas dari plafon {formatIDR(plafon)}, bukan angka bank.</span>
    </p>
  );
}

/**
 * Pemilih tenor & bunga dari master Produk KPR (per bank). Bila bank belum punya produk,
 * jatuh ke input manual dengan petunjuk menambah master — supaya form tidak buntu.
 * onChange({ product_id, product_name, tenor_months, interest_rate_pct })
 * `plafon` (opsional) → menampilkan simulasi angsuran per bulan.
 */
export default function KprTermsPicker({ bankName, value, onChange, plafon, testIdPrefix = "kpr-terms", compact = false }) {
  const [products, setProducts] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
    if (!bankName) { setProducts([]); setLoaded(true); return; }
    api.get("/master/kpr-products", { params: { bank_name: bankName } })
      .then((r) => setProducts(r.data?.data || [])).catch(() => setProducts([]))
      .finally(() => setLoaded(true));
  }, [bankName]);

  const product = useMemo(() => products.find((p) => p.id === value.product_id), [products, value.product_id]);
  const patch = (p) => onChange({ ...value, ...p });

  useEffect(() => {
    if (!loaded || !products.length || product) return;
    const p = products[0];
    patch({ product_id: p.id, product_name: p.name, interest_rate_pct: String(p.interest_rate_pct),
      tenor_months: p.tenors.includes(Number(value.tenor_months)) ? value.tenor_months : String(p.tenors[p.tenors.length - 1]) });
  }, [loaded, products]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!bankName) {
    return <p className={`text-xs text-muted-foreground ${compact ? "" : "sm:col-span-2"}`}>Pilih bank dulu — tenor & bunga mengikuti master Produk KPR bank tersebut.</p>;
  }
  if (loaded && !products.length) {
    return (
      <>
        <div className="space-y-1.5"><Label htmlFor={`${testIdPrefix}-tenor`}>Tenor (bulan)</Label>
          <Input id={`${testIdPrefix}-tenor`} data-testid={`${testIdPrefix}-tenor-manual`} type="number" value={value.tenor_months || ""}
            onChange={(e) => patch({ tenor_months: e.target.value, product_id: "", product_name: "" })} /></div>
        <div className="space-y-1.5"><Label htmlFor={`${testIdPrefix}-rate`}>Bunga (%/th)</Label>
          <Input id={`${testIdPrefix}-rate`} data-testid={`${testIdPrefix}-rate-manual`} type="number" step="0.01" value={value.interest_rate_pct || ""}
            onChange={(e) => patch({ interest_rate_pct: e.target.value, product_id: "", product_name: "" })} /></div>
        <InstallmentHint plafon={plafon} rate={value.interest_rate_pct} tenor={value.tenor_months} testId={`${testIdPrefix}-installment`} />
        <p data-testid={`${testIdPrefix}-no-master`} className="text-xs text-amber-700 sm:col-span-2">
          Belum ada Produk KPR untuk <b>{bankName}</b>. Isi manual, atau daftarkan di Konfigurasi → Master Data → <b>Produk KPR</b> agar tenor & bunga tidak diketik bebas.
        </p>
      </>
    );
  }
  return (
    <>
      <div className="space-y-1.5 sm:col-span-2"><Label>Produk KPR</Label>
        <Select value={value.product_id || ""} onValueChange={(id) => {
          const p = products.find((x) => x.id === id);
          if (p) patch({ product_id: p.id, product_name: p.name, interest_rate_pct: String(p.interest_rate_pct),
            tenor_months: p.tenors.includes(Number(value.tenor_months)) ? value.tenor_months : String(p.tenors[p.tenors.length - 1]) });
        }}>
          <SelectTrigger data-testid={`${testIdPrefix}-product`}><SelectValue placeholder={loaded ? "Pilih produk…" : "Memuat…"} /></SelectTrigger>
          <SelectContent>
            {products.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name} · {p.interest_rate_pct}%{p.fixed_years ? ` fixed ${p.fixed_years} th` : ""}{p.floating_rate_pct != null ? ` → floating ${p.floating_rate_pct}%` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5"><Label>Tenor (bulan)</Label>
        <Select value={String(value.tenor_months || "")} onValueChange={(v) => patch({ tenor_months: v })} disabled={!product}>
          <SelectTrigger data-testid={`${testIdPrefix}-tenor`}><SelectValue placeholder="Pilih tenor…" /></SelectTrigger>
          <SelectContent>
            {(product?.tenors || []).map((t) => (
              <SelectItem key={t} value={String(t)}>{t} bulan ({Math.round(t / 12 * 10) / 10} th)</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5"><Label>Bunga (%/th)</Label>
        <Input data-testid={`${testIdPrefix}-rate`} readOnly value={value.interest_rate_pct || ""} className="bg-muted" />
        {product?.min_dp_pct != null ? <p className="text-[11px] text-muted-foreground">Min. DP {product.min_dp_pct}% · {product.notes || ""}</p> : null}
      </div>
      <InstallmentHint plafon={plafon} rate={value.interest_rate_pct} tenor={value.tenor_months}
        floating={product?.floating_rate_pct} fixedYears={product?.fixed_years} testId={`${testIdPrefix}-installment`} />
    </>
  );
}
