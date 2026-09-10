import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Archive, Pencil, Plus } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import ReferenceSelect from "@/components/patterns/ReferenceSelect";
import api from "@/services/apiClient";
import { MASTER } from "@/constants/testIds";

const EMPTY = { bank_name: "", name: "", tenors: "60, 120, 180, 240", interest_rate_pct: "",
  fixed_years: "", floating_rate_pct: "", min_dp_pct: "", notes: "", is_active: true };

const parseTenors = (s) => String(s || "").split(/[,\s;]+/).map((x) => parseInt(x, 10)).filter((n) => n > 0);
const num = (v) => (v === "" || v == null ? null : Number(v));

function ProductDialog({ open, onOpenChange, product, onDone }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open) return;
    setForm(product ? {
      bank_name: product.bank_name, name: product.name, tenors: (product.tenors || []).join(", "),
      interest_rate_pct: String(product.interest_rate_pct ?? ""), fixed_years: product.fixed_years ?? "",
      floating_rate_pct: product.floating_rate_pct ?? "", min_dp_pct: product.min_dp_pct ?? "",
      notes: product.notes || "", is_active: product.is_active !== false,
    } : EMPTY);
  }, [open, product]);

  const submit = async () => {
    const tenors = parseTenors(form.tenors);
    if (!form.bank_name || !form.name.trim()) { toast.error("Bank dan nama produk wajib diisi."); return; }
    if (!tenors.length) { toast.error("Isi minimal satu tenor (bulan), pisahkan dengan koma."); return; }
    if (form.interest_rate_pct === "" || Number(form.interest_rate_pct) < 0) { toast.error("Suku bunga wajib diisi."); return; }
    setBusy(true);
    try {
      const payload = {
        bank_name: form.bank_name, name: form.name.trim(), tenors,
        interest_rate_pct: Number(form.interest_rate_pct), fixed_years: num(form.fixed_years),
        floating_rate_pct: num(form.floating_rate_pct), min_dp_pct: num(form.min_dp_pct),
        notes: form.notes || null, is_active: form.is_active,
      };
      if (product) await api.put(`/master/kpr-products/${product.id}`, payload);
      else await api.post("/master/kpr-products", payload);
      toast.success(product ? "Produk KPR diperbarui." : "Produk KPR ditambahkan.");
      onOpenChange(false);
      onDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan produk KPR.");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={MASTER.kprDialog} className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{product ? "Ubah produk KPR" : "Tambah produk KPR"}</DialogTitle>
          <DialogDescription>
            Tenor & bunga di sini menjadi pilihan pada pengajuan KPR dan SP3K — bukan diketik bebas.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Bank</Label>
            <ReferenceSelect group="financing_bank" testId={MASTER.kprFormBank}
              value={form.bank_name} onChange={(v) => set("bank_name", v)} placeholder="Pilih bank…" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kpr-prod-name">Nama produk</Label>
            <Input id="kpr-prod-name" data-testid={MASTER.kprFormName} value={form.name}
              placeholder="mis. KPR Fixed 5 Tahun" onChange={(e) => set("name", e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="kpr-prod-tenors">Tenor tersedia (bulan, pisahkan koma)</Label>
            <Input id="kpr-prod-tenors" data-testid={MASTER.kprFormTenors} value={form.tenors}
              placeholder="60, 120, 180, 240" onChange={(e) => set("tenors", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kpr-prod-rate">Bunga (%/tahun)</Label>
            <Input id="kpr-prod-rate" data-testid={MASTER.kprFormRate} type="number" step="0.01" min="0"
              value={form.interest_rate_pct} onChange={(e) => set("interest_rate_pct", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kpr-prod-fixed">Masa fixed (tahun)</Label>
            <Input id="kpr-prod-fixed" data-testid={MASTER.kprFormFixedYears} type="number" min="0"
              value={form.fixed_years} onChange={(e) => set("fixed_years", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kpr-prod-float">Bunga floating (%/tahun)</Label>
            <Input id="kpr-prod-float" data-testid={MASTER.kprFormFloating} type="number" step="0.01" min="0"
              value={form.floating_rate_pct} onChange={(e) => set("floating_rate_pct", e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kpr-prod-dp">Min. DP (%)</Label>
            <Input id="kpr-prod-dp" data-testid={MASTER.kprFormMinDp} type="number" step="0.1" min="0"
              value={form.min_dp_pct} onChange={(e) => set("min_dp_pct", e.target.value)} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="kpr-prod-notes">Catatan</Label>
            <Textarea id="kpr-prod-notes" data-testid={MASTER.kprFormNotes} rows={2} value={form.notes}
              onChange={(e) => set("notes", e.target.value)} />
          </div>
          <div className="flex items-center gap-2 sm:col-span-2">
            <Switch data-testid={MASTER.kprFormActive} checked={form.is_active} onCheckedChange={(v) => set("is_active", v)} />
            <Label>Aktif (muncul di pilihan pengajuan)</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Batal</Button>
          <Button data-testid={MASTER.kprSubmit} onClick={submit} disabled={busy}>
            {busy ? "Menyimpan…" : "Simpan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function KprProductsPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);
  const [dialog, setDialog] = useState({ open: false, product: null });

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/master/kpr-products", { params: { include_inactive: showInactive } });
      setRows(r.data?.data || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memuat produk KPR.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [showInactive]); // eslint-disable-line react-hooks/exhaustive-deps

  const archive = async (p) => {
    try {
      await api.delete(`/master/kpr-products/${p.id}`);
      toast.success(`Produk ${p.name} diarsipkan.`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengarsipkan produk.");
    }
  };

  return (
    <div data-testid={MASTER.kprPanel} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Produk KPR per bank: tenor yang tersedia dan suku bunga. Dipakai form pengajuan KPR
          (Pelanggan & Kontrak) dan tahap SP3K sebagai satu-satunya sumber tenor & bunga.
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid={MASTER.kprShowInactive} checked={showInactive} onCheckedChange={setShowInactive} />
            Tampilkan arsip
          </label>
          <Button data-testid={MASTER.kprAddBtn} size="sm" onClick={() => setDialog({ open: true, product: null })}>
            <Plus className="mr-1.5 h-4 w-4" /> Tambah produk
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Bank</th>
              <th className="px-3 py-2">Produk</th>
              <th className="px-3 py-2">Tenor (bulan)</th>
              <th className="px-3 py-2">Bunga</th>
              <th className="px-3 py-2">Min. DP</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Aksi</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">Memuat…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td data-testid={MASTER.kprEmpty} colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                Belum ada produk KPR. Tambahkan agar tenor & bunga tidak diketik bebas.
              </td></tr>
            ) : rows.map((p) => (
              <tr key={p.id} data-testid={MASTER.kprRow} data-bank={p.bank_name} className="border-t">
                <td className="px-3 py-2 font-medium">{p.bank_name}</td>
                <td className="px-3 py-2">{p.name}{p.notes ? <span className="block text-xs text-muted-foreground">{p.notes}</span> : null}</td>
                <td className="px-3 py-2">{(p.tenors || []).join(", ")}</td>
                <td className="px-3 py-2">
                  {p.interest_rate_pct}%{p.fixed_years ? ` fixed ${p.fixed_years} th` : ""}
                  {p.floating_rate_pct != null ? ` → floating ${p.floating_rate_pct}%` : ""}
                </td>
                <td className="px-3 py-2">{p.min_dp_pct != null ? `${p.min_dp_pct}%` : "—"}</td>
                <td className="px-3 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${p.is_active ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"}`}>
                    {p.is_active ? "aktif" : "arsip"}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <Button data-testid={MASTER.kprEditBtn} size="sm" variant="ghost"
                    onClick={() => setDialog({ open: true, product: p })}><Pencil className="h-3.5 w-3.5" /></Button>
                  {p.is_active ? (
                    <Button data-testid={MASTER.kprArchiveBtn} size="sm" variant="ghost" onClick={() => archive(p)}>
                      <Archive className="h-3.5 w-3.5" /></Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ProductDialog open={dialog.open} product={dialog.product}
        onOpenChange={(v) => setDialog((d) => ({ ...d, open: v }))} onDone={load} />
    </div>
  );
}
