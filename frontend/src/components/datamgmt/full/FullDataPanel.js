import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import api from "@/services/apiClient";
import { FULLDATA } from "@/constants/testIds";
import FullExportCard from "./FullExportCard";
import FullImportUpload from "./FullImportUpload";
import ImportWorkbench from "./ImportWorkbench";

/** Tab "Semua Data": ekspor seluruh koleksi ke Excel, impor balik lewat sesi viewer. */
export default function FullDataPanel({ onChanged }) {
  const [data, setData] = useState({ collections: [], groups: {}, sessions: [] });
  const [loading, setLoading] = useState(true);
  const [sessionId, setSessionId] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/data-mgmt/full/collections");
      setData(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memuat daftar koleksi.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (sessionId) {
    return (
      <ImportWorkbench sessionId={sessionId}
        onClose={() => { setSessionId(null); load(); }}
        onCommitted={() => { load(); onChanged?.(); }} />
    );
  }

  return (
    <div data-testid={FULLDATA.panel} className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <FullExportCard collections={data.collections} groups={data.groups} loading={loading} />
      <FullImportUpload sessions={data.sessions} onSession={(sid) => setSessionId(sid)} onChanged={load} />
    </div>
  );
}
