"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, History, LoaderCircle } from "lucide-react";
import { listInvestigations } from "@/lib/api";
import type { InvestigationReport } from "@/lib/types";
import { money, percent, titleCase } from "@/components/format";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export default function HistoryPage() {
  const [reports, setReports] = useState<InvestigationReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { listInvestigations().then(setReports).catch((cause: Error) => setError(cause.message)); }, []);
  return <main className="mx-auto max-w-6xl px-6 py-12"><div className="flex items-end justify-between"><div><p className="text-sm font-semibold text-emerald-700">Case archive</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Investigation history</h1></div><Link href="/upload" className="rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white">New case</Link></div>{error && <p className="mt-6 rounded-xl bg-rose-50 p-4 text-rose-700">{error}</p>}{!reports && !error && <div className="mt-10 flex items-center gap-2 text-slate-500"><LoaderCircle className="animate-spin" size={18} /> Loading history</div>}<div className="mt-7 grid gap-4">{reports?.map((report) => <Link key={report.investigation_id} href={`/investigations/${report.investigation_id}`}><Card className="transition hover:-translate-y-0.5 hover:ring-emerald-200"><div className="flex flex-col justify-between gap-4 md:flex-row md:items-center"><div className="flex items-start gap-4"><History className="mt-1 text-emerald-600" /><div><div className="flex gap-2"><Badge tone="mint">{titleCase(report.status)}</Badge><span className="font-mono text-xs text-slate-500">{report.investigation_id}</span></div><p className="mt-3 font-semibold">{report.case_files.length} case file(s) · {report.datasets.length} dataset(s)</p><p className="mt-1 text-sm text-slate-600">Monthly exposure {money(report.estimated_monthly_loss)} · confidence {percent(report.confidence)}</p></div></div><ArrowRight className="text-slate-400" /></div></Card></Link>)}{reports?.length === 0 && <Card><p className="font-semibold">No completed investigations yet.</p><p className="mt-1 text-sm text-slate-600">Upload a synthetic demo CSV set or your own data to begin.</p></Card>}</div></main>;
}
