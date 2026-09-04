"use client";

import { useRef, useState } from "react";
import { FileUp, LoaderCircle, Trash2 } from "lucide-react";
import { uploadDataset } from "@/lib/api";
import type { DatasetMetadata } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const datasetTypes = ["payments", "refunds", "discounts", "subscriptions", "invoices", "settlements"];

export function DatasetUploader() {
  const [datasets, setDatasets] = useState<DatasetMetadata[]>(() => {
    if (typeof window === "undefined") return [];
    return JSON.parse(window.sessionStorage.getItem("profit-forensics-datasets") ?? "[]") as DatasetMetadata[];
  });
  const [datasetType, setDatasetType] = useState("payments");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function save(next: DatasetMetadata[]) {
    setDatasets(next);
    window.sessionStorage.setItem("profit-forensics-datasets", JSON.stringify(next));
  }

  async function upload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return setError("Choose a CSV file to upload.");
    setUploading(true); setError(null);
    try {
      const { dataset } = await uploadDataset(file, datasetType);
      save([...datasets, dataset]);
      if (fileRef.current) fileRef.current.value = "";
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
    } finally { setUploading(false); }
  }

  return <div className="grid gap-6 lg:grid-cols-[.8fr_1.2fr]">
    <Card>
      <p className="text-sm font-semibold text-emerald-700">1. Register evidence</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Upload a dataset</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">Each uploaded CSV is inspected immediately. Only its metadata enters the investigation state.</p>
      <label className="mt-6 block text-sm font-semibold">Dataset type
        <select value={datasetType} onChange={(event) => setDatasetType(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 outline-none focus:border-emerald-500">
          {datasetTypes.map((type) => <option key={type}>{type}</option>)}
        </select>
      </label>
      <label className="mt-4 block text-sm font-semibold">CSV file
        <input ref={fileRef} type="file" accept=".csv,text/csv" className="mt-2 block w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-8 text-sm file:mr-4 file:rounded-lg file:border-0 file:bg-ink file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" />
      </label>
      {error && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <Button onClick={upload} disabled={uploading} className="mt-5 w-full" variant="mint">{uploading ? <><LoaderCircle className="animate-spin" size={17} /> Inspecting CSV</> : <><FileUp size={17} /> Upload dataset</>}</Button>
    </Card>
    <Card>
      <div className="flex items-center justify-between"><div><p className="text-sm font-semibold text-emerald-700">2. Assemble scope</p><h2 className="mt-1 text-xl font-bold">Investigation datasets</h2></div><Badge tone="mint">{datasets.length} ready</Badge></div>
      <div className="mt-5 space-y-3">
        {datasets.length === 0 && <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500">No datasets uploaded yet.</div>}
        {datasets.map((dataset) => <div key={dataset.dataset_id} className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 p-4"><div><div className="flex gap-2"><Badge>{dataset.dataset_type}</Badge><span className="text-sm font-semibold">{dataset.metadata.original_filename as string ?? "CSV dataset"}</span></div><p className="mt-2 text-xs text-slate-500">{dataset.row_count.toLocaleString()} rows · {dataset.columns.length} columns</p></div><button aria-label={`Remove ${dataset.dataset_type}`} onClick={() => save(datasets.filter((item) => item.dataset_id !== dataset.dataset_id))} className="rounded-lg p-2 text-slate-400 hover:bg-white hover:text-rose-600"><Trash2 size={17} /></button></div>)}
      </div>
    </Card>
  </div>;
}
