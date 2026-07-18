import {DatabaseZap} from "lucide-react";
import {cn} from "@/lib/utils";

export function Brand({inverse = false}: {inverse?: boolean}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-10 items-center justify-center rounded-xl bg-[var(--accent)] text-white shadow-lg shadow-indigo-950/15">
        <DatabaseZap className="size-5" />
      </div>
      <div>
        <div
          className={cn(
            "text-base font-bold tracking-tight",
            inverse ? "text-white" : "text-[var(--ink)]",
          )}
        >
          RAGForge
        </div>
        <div
          className={cn(
            "text-[11px] font-medium uppercase tracking-[0.16em]",
            inverse ? "text-slate-400" : "text-[var(--ink-faint)]",
          )}
        >
          Control plane
        </div>
      </div>
    </div>
  );
}
