import type {LucideIcon} from "lucide-react";

export function MetricCard({label, value, detail, icon: Icon}: {label: string; value: string | number; detail: string; icon: LucideIcon}) {
  return <div className="rounded-xl border border-white/[0.08] bg-[#0a1511] p-4"><div className="flex items-center justify-between"><span className="text-[10px] font-medium text-[#71847b]">{label}</span><Icon className="size-4 text-emerald-300" /></div><p className="mt-3 text-2xl font-semibold tracking-tight">{value}</p><p className="mt-1 text-[9px] text-[#53625b]">{detail}</p></div>;
}
