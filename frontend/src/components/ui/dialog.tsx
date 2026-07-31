"use client";

import {X} from "lucide-react";
import {useEffect, useRef} from "react";
import {cn} from "@/lib/utils";

export function Dialog({open, onClose, title, description, children, className}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const focusable = panelRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])');
        if (!focusable?.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
      }
    };
    document.addEventListener("keydown", listener);
    document.body.style.overflow = "hidden";
    window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("input,button")?.focus(), 10);
    return () => {
      document.removeEventListener("keydown", listener);
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;
  return <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="dialog-title" aria-describedby={description ? "dialog-description" : undefined} onMouseDown={(event) => {if (event.target === event.currentTarget) onClose();}}>
    <div ref={panelRef} className={cn("w-full max-w-lg rounded-xl border border-white/10 bg-[var(--surface-muted)] p-5 shadow-2xl sm:p-6", className)}>
      <div className="flex items-start gap-4"><div className="min-w-0 flex-1"><h2 id="dialog-title" className="text-lg font-semibold">{title}</h2>{description ? <p id="dialog-description" className="mt-1.5 text-sm leading-6 text-[var(--ink-muted)]">{description}</p> : null}</div><button onClick={onClose} className="icon-button -mr-2 -mt-2" aria-label="Close dialog"><X className="size-4" /></button></div>
      {children}
    </div>
  </div>;
}
