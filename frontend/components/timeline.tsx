import { CheckCircle2, CircleDot, Timer } from "lucide-react";
import type { TimelineEvent } from "@/lib/types";
import { titleCase } from "@/components/format";

export function Timeline({ events, pending = [] }: { events: TimelineEvent[]; pending?: string[] }) {
  return <ol className="space-y-4">{events.map((event) => <li key={event.id} className="relative flex gap-3"><CheckCircle2 className="mt-0.5 shrink-0 text-emerald-600" size={19} /><div><div className="flex flex-wrap items-center gap-2"><p className="font-semibold">{event.title}</p><span className="text-xs text-slate-400">{Math.round(event.progress * 100)}%</span></div>{event.description && <p className="mt-1 text-sm leading-5 text-slate-600">{event.description}</p>}</div></li>)}{pending.map((stage, index) => <li key={stage} className="flex gap-3 text-slate-500"><span className="mt-0.5 grid h-5 w-5 place-items-center rounded-full border border-slate-300">{index === 0 ? <Timer size={12} /> : <CircleDot size={11} />}</span><div><p className="font-semibold">{titleCase(stage)}</p><p className="mt-1 text-sm">Waiting for the authoritative graph update.</p></div></li>)}</ol>;
}
