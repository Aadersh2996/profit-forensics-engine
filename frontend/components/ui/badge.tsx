import { cn } from "@/lib/utils";

export function Badge({ children, tone = "slate" }: { children: React.ReactNode; tone?: "slate" | "mint" | "amber" | "rose" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-600",
    mint: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700"
  };
  return <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold", tones[tone])}>{children}</span>;
}
