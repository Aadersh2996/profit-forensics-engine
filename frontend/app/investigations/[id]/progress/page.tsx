"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, LoaderCircle, Radio } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Timeline } from "@/components/timeline";
import { getInvestigation } from "@/lib/api";

const stages = ["Case creation", "Planner selection", "Investigator execution", "Confidence and evidence refinement", "Financial impact", "Recommendations and executive report"];

export default function InvestigationProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [checks, setChecks] = useState(0);
  useEffect(() => {
    let attempts = 0;
    const check = async () => {
      try {
        const report = await getInvestigation(id);
        sessionStorage.setItem(`profit-forensics-report-${id}`, JSON.stringify(report));
        router.replace(`/investigations/${id}`);
      } catch {
        attempts += 1;
        setChecks(attempts);
        if (attempts < 20) window.setTimeout(check, 750);
        else setError("The server has not returned a completed investigation. Confirm that the API is running and try again.");
      }
    };
    check();
  }, [id, router]);
  return <main className="mx-auto max-w-4xl px-6 py-12"><Card className="overflow-hidden p-0"><div className="border-b border-slate-100 bg-gradient-to-r from-emerald-50 to-white p-6 md:p-8"><div className="flex items-start gap-4"><div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-ink text-mint shadow-lg shadow-slate-300"><Activity size={22} /></div><div><p className="text-sm font-semibold text-emerald-700">Live investigation status</p><h1 className="mt-1 text-2xl font-bold md:text-3xl">{id}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">The existing LangGraph workflow is running on the backend. This page only reflects authoritative persisted state and automatically opens the report when it is available.</p></div></div></div><div className="p-6 md:p-8">{error ? <div className="rounded-xl bg-rose-50 p-4 text-rose-700"><div className="flex gap-2 font-semibold"><AlertTriangle size={18} /> Investigation could not be completed</div><p className="mt-2 text-sm">{error}</p><Link href="/investigations/new" className="mt-4 inline-block text-sm font-semibold underline">Return to case setup</Link></div> : <><div className="flex flex-col justify-between gap-3 rounded-xl border border-emerald-100 bg-emerald-50/70 p-4 sm:flex-row sm:items-center"><div className="flex items-center gap-3 text-sm font-semibold text-emerald-900"><span className="relative flex h-3 w-3"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" /><span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-600" /></span>Backend execution active</div><span className="flex items-center gap-2 text-xs font-medium text-emerald-800"><Radio size={14} /> Polling persisted report · check {checks + 1}</span></div><div className="mt-7 grid gap-5 lg:grid-cols-[1.35fr_.65fr]"><div><h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">Authoritative milestones</h2><div className="mt-4"><Timeline events={[]} pending={stages} /></div></div><div className="rounded-2xl bg-slate-50 p-5"><LoaderCircle className="animate-spin text-emerald-600" size={22} /><h2 className="mt-4 font-bold">What is happening now</h2><p className="mt-2 text-sm leading-6 text-slate-600">The API does not stream intermediate graph state, so this view intentionally avoids invented progress. On completion, it loads the planner decisions, evidence confidence, financial impact, and the final timeline.</p><div className="mt-5 border-t border-slate-200 pt-4 text-sm text-slate-600"><CheckCircle2 className="mr-2 inline text-emerald-600" size={16} />No analysis is performed in the browser.</div></div></div></>}</div></Card></main>;
}
