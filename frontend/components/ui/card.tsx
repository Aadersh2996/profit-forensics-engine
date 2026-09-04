import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("rounded-2xl bg-white p-5 shadow-panel ring-1 ring-slate-100", className)} {...props} />;
}
