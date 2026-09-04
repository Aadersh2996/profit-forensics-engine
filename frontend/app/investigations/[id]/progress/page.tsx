"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, AlertTriangle, LoaderCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Timeline } from "@/components/timeline";
import { getInvestigation } from "@/lib/api";

const stages = ["case creation", "planner selection", "investigator execution", "confidence and evidence refinement", "financial impact", "recommendations and executive report"];

export default function InvestigationProgressPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let attempts = 0;
    const check = async () => {
      try {
        const report = await getInvestigation(id);
        sessionStorage.setItem(`profit-forensics-report-${id}`, JSON.stringify(report));
        router.replace(`/investigations/${id}`);
      } catch {
        attempts += 1;
        if (attempts < 20) window.setTimeout(check, 750);
        else setError("The server has not returned a completed investigation. Confirm that the API is running and try again.");
      }
    };
    check();
  }, [id, router]);
  return <main className="mx-auto max-w-3xl px-6 py-12"><Card><div className="flex items-start gap-4"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-ink text-mint"><Activity size={21} /></div><div><p className="text-sm font-semibold text-emerald-700">Investigation in progress</p><h1 className="mt-1 text-2xl font-bold">{id}</h1><p className="mt-2 text-sm leading-6 text-slate-600">The graph runs on the backend and this screen will switch to the completed case dashboard when the server returns its report.</p></div></div>{error ? <div className="mt-7 rounded-xl bg-rose-50 p-4 text-rose-700"><div className="flex gap-2 font-semibold"><AlertTriangle size={18} /> Investigation could not be completed</div><p className="mt-2 text-sm">{error}</p><Link href="/investigations/new" className="mt-4 inline-block text-sm font-semibold underline">Return to case setup</Link></div> : <><div className="mt-7 flex items-center gap-2 rounded-xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-800"><LoaderCircle size={18} className="animate-spin" /> Waiting for graph completion</div><div className="mt-7"><Timeline events={[]} pending={stages} /></div></>}</Card></main>;
}
