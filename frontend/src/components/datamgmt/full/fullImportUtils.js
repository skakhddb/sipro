import api from "@/services/apiClient";

export const LEVEL = {
  error: { label: "Error", cell: "bg-rose-100 ring-1 ring-inset ring-rose-400 text-rose-900", chip: "bg-rose-50 text-rose-800 border-rose-200", dot: "bg-rose-500" },
  warning: { label: "Peringatan", cell: "bg-amber-100 ring-1 ring-inset ring-amber-400 text-amber-900", chip: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
  info: { label: "Info", cell: "bg-sky-50 ring-1 ring-inset ring-sky-300 text-sky-900", chip: "bg-sky-50 text-sky-800 border-sky-200", dot: "bg-sky-500" },
};

export const STATUS = {
  insert: { label: "Baru", cls: "bg-emerald-50 text-emerald-800 border-emerald-200" },
  update: { label: "Diubah", cls: "bg-sky-50 text-sky-800 border-sky-200" },
  same: { label: "Sama", cls: "bg-secondary text-muted-foreground border-transparent" },
  error: { label: "Error", cls: "bg-rose-50 text-rose-800 border-rose-200" },
};

/** Tingkat tertinggi dari daftar temuan sebuah sel. */
export function topLevel(issues) {
  if (issues.some((i) => i.level === "error")) return "error";
  if (issues.some((i) => i.level === "warning")) return "warning";
  if (issues.length) return "info";
  return null;
}

export function cellText(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Nilai input pengguna → nilai sel (kosong = null, angka & TRUE/FALSE dikenali). */
export function parseInput(text) {
  const s = text.trim();
  if (s === "") return null;
  if (/^-?\d+$/.test(s) && s.length < 16) return parseInt(s, 10);
  if (/^-?\d+\.\d+$/.test(s)) return parseFloat(s);
  return s;
}

export const sessionApi = {
  report: (sid) => api.get(`/data-mgmt/full/sessions/${sid}`).then((r) => r.data),
  sheet: (sid, sheet, params) => api.get(`/data-mgmt/full/sessions/${sid}/sheets/${encodeURIComponent(sheet)}`, { params }).then((r) => r.data),
  edit: (sid, edits) => api.patch(`/data-mgmt/full/sessions/${sid}/cells`, { edits }).then((r) => r.data),
  deleteRows: (sid, sheet, rows) => api.post(`/data-mgmt/full/sessions/${sid}/delete-rows`, { sheet, rows }).then((r) => r.data),
  commit: (sid, body) => api.post(`/data-mgmt/full/sessions/${sid}/commit`, body).then((r) => r.data),
  remove: (sid) => api.delete(`/data-mgmt/full/sessions/${sid}`).then((r) => r.data),
};
