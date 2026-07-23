import type {LucideIcon} from "lucide-react";

export function MetricCard({label, value, detail, icon: Icon}: {label: string; value: string | number; detail: string; icon: LucideIcon}) {
  return <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-sm)] transition hover:border-[var(--border-strong)] hover:bg-[var(--surface-muted)]"><div className="flex items-center justify-between"><span className="text-[13px] font-medium text-[var(--ink-muted)]">{label}</span><Icon className="size-4 text-[var(--accent)]" /></div><p className="mt-3 text-[26px] font-semibold leading-[1.1] tracking-[-0.025em] text-[var(--ink)]">{value}</p><p className="mt-1 text-xs leading-5 text-[var(--ink-faint)]">{detail}</p></div>;
}
