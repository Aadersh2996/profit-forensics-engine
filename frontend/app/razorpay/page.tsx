"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, CloudDownload, KeyRound, LoaderCircle, ShieldCheck } from "lucide-react";
import { connectRazorpay, getRazorpayStatus, syncRazorpay } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const resourceOptions = ["payments", "refunds", "orders", "customers", "subscriptions", "invoices", "settlements"];

export default function RazorpayPage() {
  const router = useRouter();
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [selected, setSelected] = useState(["payments", "refunds", "subscriptions", "invoices", "settlements"]);
  const [connection, setConnection] = useState<string | null>(null);
  const [busy, setBusy] = useState<"connect" | "sync" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { getRazorpayStatus().then((status) => status.configured && setConnection("Environment credentials are available.")).catch(() => undefined); }, []);
  const credentials = { key_id: keyId.trim(), key_secret: keySecret };
  const canSubmit = credentials.key_id.length > 0 && credentials.key_secret.length > 0;

  function toggle(resource: string) {
    setSelected((items) => items.includes(resource) ? items.filter((item) => item !== resource) : [...items, resource]);
  }

  async function connect() {
    if (!canSubmit) return setError("Enter a Razorpay Key ID and Key Secret.");
    setBusy("connect"); setError(null);
    try { setConnection((await connectRazorpay(credentials)).message); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Connection validation failed."); }
    finally { setBusy(null); }
  }

  async function syncAndInvestigate() {
    if (!canSubmit) return setError("Enter credentials before synchronizing.");
    if (!selected.length) return setError("Select at least one resource.");
    setBusy("sync"); setError(null);
    try {
      const result = await syncRazorpay(credentials, selected);
      keySecret && setKeySecret("");
      if (result.investigation) {
        sessionStorage.setItem(`profit-forensics-report-${result.investigation.investigation_id}`, JSON.stringify(result.investigation));
        router.push(`/investigations/${result.investigation.investigation_id}`);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Razorpay synchronization failed."); }
    finally { setBusy(null); }
  }

  return <main className="mx-auto max-w-5xl px-6 py-12"><div className="mb-8 max-w-2xl"><Badge tone="mint">Additional ingestion source</Badge><h1 className="mt-3 text-3xl font-bold tracking-tight">Connect Razorpay</h1><p className="mt-3 leading-7 text-slate-600">Fetch read-only Razorpay records, normalize them into the same dataset contract as CSVs, and use the existing deterministic investigation workflow.</p></div><div className="grid gap-6 lg:grid-cols-[.9fr_1.1fr]"><Card><div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><KeyRound size={20} /></div><div><h2 className="font-bold">1. Validate access</h2><p className="text-sm text-slate-600">Credentials are used only for this browser request and are never stored.</p></div></div><label className="mt-6 block text-sm font-semibold">Key ID<input autoComplete="off" value={keyId} onChange={(event) => setKeyId(event.target.value)} placeholder="rzp_live_..." className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2.5 font-mono text-sm outline-none focus:border-emerald-500" /></label><label className="mt-4 block text-sm font-semibold">Key Secret<input autoComplete="off" type="password" value={keySecret} onChange={(event) => setKeySecret(event.target.value)} placeholder="••••••••" className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2.5 font-mono text-sm outline-none focus:border-emerald-500" /></label><Button onClick={connect} disabled={busy !== null} variant="mint" className="mt-5 w-full">{busy === "connect" ? <><LoaderCircle className="animate-spin" size={17} /> Validating</> : <><ShieldCheck size={17} /> Validate connection</>}</Button>{connection && <p className="mt-4 flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 size={16} />{connection}</p>}</Card><Card><div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-slate-700"><CloudDownload size={20} /></div><div><h2 className="font-bold">2. Synchronize and investigate</h2><p className="text-sm text-slate-600">Only selected resources are fetched, normalized, and sent to the planner.</p></div></div><div className="mt-6 grid gap-2 sm:grid-cols-2">{resourceOptions.map((resource) => <label key={resource} className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 p-3 text-sm font-semibold capitalize hover:bg-slate-50"><input type="checkbox" checked={selected.includes(resource)} onChange={() => toggle(resource)} className="h-4 w-4 accent-emerald-600" />{resource}</label>)}</div><Button onClick={syncAndInvestigate} disabled={busy !== null} className="mt-6 w-full">{busy === "sync" ? <><LoaderCircle className="animate-spin" size={17} /> Fetching and investigating</> : <><CloudDownload size={17} /> Sync Razorpay and run investigation</>}</Button>{error && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}</Card></div></main>;
}
