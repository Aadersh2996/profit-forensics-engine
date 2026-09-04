import Link from "next/link";
import { ArrowRight, CheckCircle2, FileSearch, ShieldCheck, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { WorkflowGraph } from "@/components/workflow-graph";

const capabilities = [
  ["Deterministic controls", "Trace every amount, confidence score, and routing decision back to supplied records."],
  ["Five focused investigators", "Examine payment recovery, refunds, discounts, subscriptions, and invoices."],
  ["Evidence-led synthesis", "Reserve optional LLM use for root causes, recommendations, and reporting."],
];

export default function HomePage() {
  return <main className="mx-auto max-w-7xl px-6 py-16">
    <section className="grid items-center gap-12 lg:grid-cols-[1.1fr_.9fr]">
      <div>
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700"><Sparkles size={15} /> Buildathon demo ready</div>
        <h1 className="max-w-3xl text-5xl font-bold tracking-[-0.04em] text-ink md:text-6xl">Find the financial signals hiding in your operations.</h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">Profit Forensics turns CSV records into deterministic cases, traceable financial impact, and clear next actions—without letting an LLM do the math.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/upload" className="inline-flex items-center gap-2 rounded-xl bg-ink px-5 py-3 font-semibold text-white shadow-lg shadow-slate-300 transition hover:bg-slate-800">Start with CSVs <ArrowRight size={17} /></Link>
          <Link href="/history" className="rounded-xl border border-slate-200 bg-white px-5 py-3 font-semibold text-slate-700 transition hover:bg-slate-50">View investigations</Link>
        </div>
      </div>
      <Card className="p-3"><WorkflowGraph /><div className="grid grid-cols-3 gap-3 p-3 text-center text-xs font-semibold text-slate-500"><span>DATA IN</span><span>DETERMINISTIC ANALYSIS</span><span>DECISION READY</span></div></Card>
    </section>
    <section className="mt-20 grid gap-5 md:grid-cols-3">
      {capabilities.map(([title, description], index) => {
        const Icon = [ShieldCheck, FileSearch, CheckCircle2][index];
        return <Card key={title}><Icon className="mb-5 text-emerald-600" /><h2 className="text-lg font-bold">{title}</h2><p className="mt-2 leading-6 text-slate-600">{description}</p></Card>;
      })}
    </section>
  </main>;
}
