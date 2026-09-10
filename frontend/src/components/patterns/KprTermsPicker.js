import React, { useEffect, useMemo, useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/services/apiClient";

/**
 * Pemilih tenor & bunga dari master Produk KPR (per bank). Bila bank belum punya produk,
 * jatuh ke input manual dengan petunjuk menambah master — supaya form tidak buntu.
 * onChange({ product_id, product_name, tenor_months, interest_rate_pct })
 */
export default function KprTermsPicker({ bankName, value, onChange, testIdPrefix = "kpr-terms", compact = false }) {
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
    </>
  );
}
