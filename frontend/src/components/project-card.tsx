"use client";

import {Activity, ArrowRight, FileStack, FolderKanban, MoreHorizontal, Pencil, Trash2} from "lucide-react";
import Link from "next/link";
import {useState} from "react";
import {StatusBadge} from "@/components/status-badge";
import type {Project} from "@/lib/types";
import {cn, relativeTime} from "@/lib/utils";

export function ProjectCard({project, documentCount, activeRuns, view, onRename, onDelete}: {
  project: Project;
  documentCount: number | null;
  activeRuns: number | null;
  view: "grid" | "list";
  onRename: () => void;
  onDelete: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const status = activeRuns ? "processing" : "ready";
  return <article className={cn("group relative rounded-xl border border-white/[0.08] bg-[var(--surface)] transition hover:border-[var(--accent-border)]", view === "grid" ? "p-5" : "flex items-center gap-4 p-4")}>
    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]"><FolderKanban className="size-5" /></span>
    <div className={cn("min-w-0 flex-1", view === "grid" && "mt-4")}>
      <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h2 className="truncate text-sm font-semibold">{project.name}</h2><p className="mt-1 text-[10px] text-[#64736d]">Updated {relativeTime(project.updated_at)}</p></div><StatusBadge status={status} /></div>
      <p className={cn("text-[11px] leading-5 text-[#83948c]", view === "grid" ? "mt-3 line-clamp-2 min-h-10" : "mt-1 line-clamp-1")}>An isolated knowledge base for indexed documents, grounded answers, and retrieval traces.</p>
      <div className="mt-4 flex flex-wrap items-center gap-4 text-[10px] text-[#71847b]"><span className="flex items-center gap-1.5"><FileStack className="size-3" />{documentCount === null ? "…" : documentCount} documents</span><span className="flex items-center gap-1.5"><Activity className="size-3" />{activeRuns === null ? "…" : activeRuns ? `${activeRuns} active` : "No active runs"}</span></div>
    </div>
    <div className={cn("flex items-center gap-2", view === "grid" ? "mt-5 border-t border-white/[0.07] pt-4" : "shrink-0")}>
      <Link href={`/projects/${project.project_id}/documents`} className="flex h-9 flex-1 items-center justify-center gap-2 rounded-lg bg-[var(--accent-soft)] px-3 text-[11px] font-medium text-[var(--accent-hover)] hover:bg-[var(--accent-muted)]">Open workspace<ArrowRight className="size-3.5" /></Link>
      <div className="relative"><button className="icon-button" onClick={() => setMenuOpen((value) => !value)} aria-label={`Actions for ${project.name}`} aria-expanded={menuOpen}><MoreHorizontal className="size-4" /></button>{menuOpen ? <div className="popover bottom-11 right-0 w-40 p-1"><button className="menu-item w-full" onClick={() => {setMenuOpen(false); onRename();}}><Pencil className="size-3.5" />Rename</button><button className="menu-item w-full text-red-300" onClick={() => {setMenuOpen(false); onDelete();}}><Trash2 className="size-3.5" />Delete</button></div> : null}</div>
    </div>
  </article>;
}
