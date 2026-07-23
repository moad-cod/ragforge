import type {HTMLAttributes} from "react";
import {cn} from "@/lib/utils";

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold",
        tone === "neutral" && "border-[var(--border)] bg-white/[0.04] text-[var(--ink-muted)]",
        tone === "success" && "border-[var(--success-border)] bg-[var(--success-soft)] text-[#b9cce2]",
        tone === "warning" && "border-[var(--warning-border)] bg-[var(--warning-soft)] text-[#e3bd7d]",
        tone === "danger" && "border-[var(--danger-border)] bg-[var(--danger-soft)] text-[#e89a9a]",
        tone === "info" && "border-[var(--info-border)] bg-[var(--info-soft)] text-[#c3cfdd]",
        className,
      )}
      {...props}
    />
  );
}
