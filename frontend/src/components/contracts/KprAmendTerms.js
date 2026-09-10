import React, { useEffect, useState } from "react";
import { FileClock, History } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import EvidenceUploader from "@/components/patterns/EvidenceUploader";
import KprTermsPicker from "@/components/patterns/KprTermsPicker";
import KprScheduleTable from "@/components/patterns/KprScheduleTable";
import { formatDateWIB } from "@/utils/formatters";
import api from "@/services/apiClient";

const T = {
  amendBtn: "kpr-amend-btn", dialog: "kpr-amend-dialog", reason: "kpr-amend-reason", submit: "kpr-amend-submit",
  historyRow: "kpr-amendment-row", scheduleBox: "kpr-schedule-box", scheduleRow: "kpr-schedule-row",
};
export const KPR_AMEND_TESTIDS = T;

/** Dialog amandemen tenor/bunga/produk sesudah SP3K — bank mengubah ketentuan, riwayat tersimpan. */
export function KprAmendTermsDialog({ contract, app, open, onOpenChange, onChanged }) {
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setForm({ product_id: app.kpr_product_id || "", product_name: app.kpr_product_name || "",
      tenor_months: app.tenor_months ? String(app.tenor_months) : "", rate: app.interest_rate_pct ? String(app.interest_rate_pct) : "", reason: "" });
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/contracts/${contract.id}/kpr/amend-terms`, {
        tenor_months: Number(form.tenor_months || 0), rate: Number(form.rate || 0),
        kpr_product_id: form.product_id || null, kpr_product_name: form.product_name || null,
        reason: form.reason || "", file_id: form.file_id || null,
      });
      toast.success("Amandemen tenor/bunga KPR tercatat.");
      onOpenChange(false);
      onChanged && onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat amandemen.");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={T.dialog} className="max-h-[85vh] max-w-md overflow-y-auto bg-background">
        <DialogHeader>
          <DialogTitle>Amandemen ketentuan KPR</DialogTitle>
          <DialogDescription>
            Bank {app.bank_name} mengubah tenor/bunga sesudah SP3K. Ketentuan lama tetap tersimpan di riwayat;
            jadwal angsuran pembeli mengikuti ketentuan baru.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <KprTermsPicker bankName={app.bank_name || ""} testIdPrefix="kpr-amend-terms" plafon={app.approved_plafon}
              value={{ product_id: form.product_id || "", product_name: form.product_name || "", tenor_months: form.tenor_months || "", interest_rate_pct: form.rate || "" }}
              onChange={(v) => setForm((f) => ({ ...f, product_id: v.product_id, product_name: v.product_name, tenor_months: v.tenor_months, rate: v.interest_rate_pct }))} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="kpr-amend-reason">Alasan (wajib, min. 5 huruf)</Label>
            <Textarea id="kpr-amend-reason" data-testid={T.reason} rows={2} className="bg-background" value={form.reason || ""}
              placeholder="mis. Bank menurunkan bunga promo / pembeli memperpanjang tenor"
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} />
          </div>
          <EvidenceUploader ownerType="contract" ownerId={contract.id} max={1} label="Surat/addendum bank (opsional)"
            value={form.files || []} onChange={(ids) => setForm((f) => ({ ...f, files: ids, file_id: ids[0] || undefined }))} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Batal</Button>
          <Button data-testid={T.submit} onClick={submit} disabled={busy || (form.reason || "").trim().length < 5}>
            {busy ? "Menyimpan…" : "Catat amandemen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Riwayat amandemen (lama → baru) di panel KPR staf. */
export function KprAmendmentHistory({ items }) {
  if (!items?.length) return null;
  return (
    <div className="space-y-1 rounded-lg border bg-background p-3 text-xs">
      <p className="flex items-center gap-1.5 font-medium"><History className="h-3.5 w-3.5" /> Riwayat amandemen ketentuan</p>
      {items.slice().reverse().map((a, i) => (
        <p key={i} data-testid={T.historyRow} className="text-muted-foreground">
          {formatDateWIB(a.at)} · {a.by}: tenor {a.before?.tenor_months}→<b>{a.after?.tenor_months}</b> bln, bunga {a.before?.interest_rate_pct}→<b>{a.after?.interest_rate_pct}%</b>
          {a.after?.kpr_product_name && a.after.kpr_product_name !== a.before?.kpr_product_name ? <>, produk <b>{a.after.kpr_product_name}</b></> : null} — {a.reason}
        </p>
      ))}
    </div>
  );
}

/** Kotak jadwal angsuran (simulasi) — data dari GET /contracts/{id}/kpr/schedule. */
export function KprScheduleBox({ contract, nonce }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    api.get(`/contracts/${contract.id}/kpr/schedule`).then((r) => setData(r.data.data)).catch(() => setData(null));
  }, [contract.id, nonce]);
  if (!data?.available) return null;
  return (
    <div data-testid={T.scheduleBox} className="space-y-2 rounded-lg border bg-background p-3">
      <button type="button" className="flex w-full items-center justify-between text-sm font-medium" onClick={() => setOpen((v) => !v)}>
        <span className="flex items-center gap-1.5"><FileClock className="h-4 w-4" /> Jadwal angsuran (simulasi) — {data.tenor_months} bulan @ {data.interest_rate_pct}%</span>
        <span className="text-xs text-muted-foreground">{open ? "sembunyikan" : "tampilkan"}</span>
      </button>
      {open ? <KprScheduleTable data={data} rowTestId={T.scheduleRow} compact /> : null}
    </div>
  );
}
