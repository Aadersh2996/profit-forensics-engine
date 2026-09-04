import Link from "next/link";
import { ArrowRight, CheckCircle2, FileSearch, PlayCircle, ShieldCheck, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { WorkflowGraph } from "@/components/workflow-graph";

const capabilities = [
  { title: "Deterministic by design", description: "Every routing decision, confidence score, and financial estimate is reproducible from the supplied records.", Icon: ShieldCheck },
  { title: "Five focused investigators", description: "Detect payment recovery, refunds, discount leakage, subscriptions, and revenue collection opportunities.", Icon: FileSearch },
  { title: "Decision-ready evidence", description: "Review traceable case files, impact, recommendations, and an executive report without letting an LLM do the maths.", Icon: CheckCircle2 },
];

const proofPoints = ["CSV, Razorpay REST, and verified webhooks", "One bounded evidence-refinement retry", "₹ values stay deterministic and traceable"];

export default function HomePage() {
  return <main className="overflow-hidden">
    <section className="relative border-b border-slate-200 bg-gradient-to-b from-emerald-50 via-canvas to-canvas">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-16 lg:grid-cols-[1.06fr_.94fr] lg:py-24">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white/80 px-3 py-1.5 text-sm font-semibold text-emerald-700 shadow-sm"><Sparkles size={15} /> Razorpay AI Buildathon · demo-ready</div>
          <h1 className="max-w-3xl text-5xl font-bold tracking-[-0.055em] text-ink md:text-6xl lg:text-7xl">Turn payment operations into <span className="text-emerald-600">clear financial action.</span></h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-slate-600">Profit Forensics investigates operational data with deterministic controls, then turns evidence into traceable cases, financial impact, and focused next actions.</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link href="/upload?demo=1" className="inline-flex items-center gap-2 rounded-xl bg-ink px-5 py-3 font-semibold text-white shadow-lg shadow-slate-300 transition hover:-translate-y-0.5 hover:bg-slate-800"><PlayCircle size={18} /> Run demo dataset <ArrowRight size={17} /></Link>
            <Link href="/upload" className="rounded-xl border border-slate-200 bg-white px-5 py-3 font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50">Upload CSVs</Link>
            <Link href="/razorpay" className="rounded-xl border border-slate-200 bg-white px-5 py-3 font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50">Connect Razorpay</Link>
          </div>
          <p className="mt-4 text-sm text-slate-500">The bundled synthetic datasets load through the normal CSV ingestion path—no mock investigation results.</p>
        </div>
        <Card className="relative overflow-hidden p-3 shadow-2xl shadow-slate-200/70"><div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-400 via-mint to-cyan-400" /><WorkflowGraph /><div className="grid grid-cols-3 gap-3 px-3 pb-3 pt-5 text-center text-xs font-semibold tracking-wide text-slate-500"><span>DATA IN</span><span>DETERMINISTIC ANALYSIS</span><span>DECISION READY</span></div></Card>
      </div>
    </section>
    <section className="mx-auto max-w-7xl px-6 py-14"><div className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-panel md:grid-cols-3">{proofPoints.map((point) => <div key={point} className="flex items-center gap-3 text-sm font-semibold text-slate-700"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-700"><CheckCircle2 size={16} /></span>{point}</div>)}</div></section>
    <section className="mx-auto max-w-7xl px-6 pb-20"><div className="max-w-2xl"><p className="text-sm font-semibold text-emerald-700">Why it matters</p><h2 className="mt-2 text-3xl font-bold tracking-tight">Built for fast, defensible financial investigation.</h2><p className="mt-3 leading-7 text-slate-600">Payment operations fail in patterns. The engine isolates those patterns while keeping the evidence and calculations visible to the people who need to act.</p></div><div className="mt-9 grid gap-5 md:grid-cols-3">{capabilities.map(({ title, description, Icon }) => <Card key={title} className="group border border-slate-100 p-6 transition duration-200 hover:-translate-y-1 hover:ring-emerald-200"><div className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-50 text-emerald-700 transition group-hover:bg-emerald-100"><Icon size={21} /></div><h3 className="mt-5 text-lg font-bold">{title}</h3><p className="mt-2 leading-6 text-slate-600">{description}</p></Card>)}</div></section>
  </main>;
}
