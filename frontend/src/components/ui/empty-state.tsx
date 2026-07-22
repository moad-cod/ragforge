import type {LucideIcon} from "lucide-react";
import {Button} from "@/components/ui/button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  onAction,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border-strong)] bg-white/[0.015] px-6 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent)]">
        <Icon className="size-6" />
      </div>
      <h3 className="text-base font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-[var(--ink-muted)]">
        {description}
      </p>
      {action && onAction ? (
        <Button className="mt-5" onClick={onAction}>
          {action}
        </Button>
      ) : null}
    </div>
  );
}
