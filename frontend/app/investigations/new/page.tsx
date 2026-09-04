"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, ClipboardCheck, LoaderCircle } from "lucide-react";
import { createInvestigation } from "@/lib/api";
import type { DatasetMetadata } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function NewInvestigationPage() {
  const router = useRouter();
  const [id, setId] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const datasets: DatasetMetadata[] = typeof window === "undefined" ? [] : JSON.parse(sessionStorage.getItem("profit-forensics-datasets") ?? "[]");
  async function start() {
    if (!datasets.length) return setError("Upload at least one CSV dataset before starting.");
    setRunning(true); setError(null);
    const provisionalId = id.trim() || `PF-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
    sessionStorage.setItem("profit-forensics-running", provisionalId);
    router.push(`/investigations/${provisionalId}/progress`);
    try {
      const report = await createInvestigation(datasets, provisionalId);
      sessionStorage.setItem(`profit-forensics-report-${report.investigation_id}`, JSON.stringify(report));
      router.replace(`/investigations/${report.investigation_id}`);
    } catch (cause) {
      sessionStorage.setItem("profit-forensics-error", cause instanceof Error ? cause.message : "Investigation failed.");
      router.replace(`/investigations/${provisionalId}/progress`);
    } finally { setRunning(false); }
  }
  return <main className="mx-auto max-w-4xl px-6 py-12"><Card className="mx-auto max-w-2xl"><div className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><ClipboardCheck size={22} /></div><p className="mt-5 text-sm font-semibold text-emerald-700">Ready to investigate</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Create a forensic case</h1><p className="mt-3 leading-7 text-slate-600">The planner will select only the deterministic investigators supported by the uploaded metadata.</p><label className="mt-6 block text-sm font-semibold">Optional case ID<input value={id} onChange={(event) => setId(event.target.value)} placeholder="PF-DEMO-001" className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2.5 font-mono text-sm outline-none focus:border-emerald-500" /></label><div className="mt-6 flex flex-wrap gap-2">{datasets.map((dataset) => <Badge key={dataset.dataset_id} tone="mint">{dataset.dataset_type} · {dataset.row_count} rows</Badge>)}</div>{error && <p className="mt-5 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<Button className="mt-7 w-full" onClick={start} disabled={running}>{running ? <><LoaderCircle className="animate-spin" size={17} /> Starting investigation</> : <>Launch investigation <ArrowRight size={17} /></>}</Button></Card></main>;
}
