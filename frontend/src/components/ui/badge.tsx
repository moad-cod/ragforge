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
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        tone === "neutral" && "bg-white/[0.06] text-[#93a39c]",
        tone === "success" && "bg-emerald-400/10 text-emerald-300",
        tone === "warning" && "bg-amber-400/10 text-amber-300",
        tone === "danger" && "bg-red-400/10 text-red-300",
        tone === "info" && "bg-blue-400/10 text-blue-300",
        className,
      )}
      {...props}
    />
  );
}
