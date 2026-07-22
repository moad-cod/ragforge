import * as React from "react";
import {cn} from "@/lib/utils";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  ...props
}: Props) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2",
        variant === "primary" &&
          "bg-[var(--accent)] text-[#041d13] shadow-sm hover:bg-[var(--accent-strong)]",
        variant === "secondary" &&
          "border border-[var(--border)] bg-[var(--surface-muted)] text-[var(--ink)] hover:bg-[var(--surface-hover)]",
        variant === "ghost" &&
          "text-[var(--ink-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]",
        variant === "danger" &&
          "border border-red-400/20 bg-[var(--danger-soft)] text-red-300 hover:bg-red-400/15",
        size === "sm" && "h-9 px-3 text-sm",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-11 px-5 text-sm",
        size === "icon" && "size-10",
        className,
      )}
      {...props}
    />
  );
}
