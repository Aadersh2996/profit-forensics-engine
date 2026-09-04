import Link from "next/link";
import { ArrowUpRight, BarChart3 } from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink text-mint"><BarChart3 size={18} /></span>
            Profit Forensics
          </Link>
          <div className="flex items-center gap-5 text-sm font-medium text-slate-600">
            <Link href="/upload" className="hover:text-ink">Upload data</Link>
            <Link href="/investigations/new" className="hover:text-ink">New investigation</Link>
            <Link href="/history" className="hover:text-ink">History</Link>
            <a href="/api/docs" target="_blank" className="hidden items-center gap-1 hover:text-ink md:flex">API <ArrowUpRight size={14} /></a>
          </div>
        </nav>
      </header>
      {children}
    </div>
  );
}
