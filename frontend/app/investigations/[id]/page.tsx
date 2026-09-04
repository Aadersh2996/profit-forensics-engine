"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { getInvestigation } from "@/lib/api";
import type { InvestigationReport } from "@/lib/types";
import { ReportDashboard } from "@/components/report-dashboard";

export default function InvestigationPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getInvestigation(id).then(setReport).catch((cause: Error) => setError(cause.message)); }, [id]);
  if (error) return <main className="mx-auto max-w-5xl px-6 py-12"><p className="rounded-xl bg-rose-50 p-4 text-rose-700">{error}</p></main>;
  if (!report) return <main className="grid min-h-[60vh] place-items-center"><div className="flex items-center gap-2 text-slate-500"><LoaderCircle className="animate-spin" size={19} /> Loading case report</div></main>;
  return <main className="mx-auto max-w-7xl px-6 py-10"><ReportDashboard report={report} /></main>;
}
