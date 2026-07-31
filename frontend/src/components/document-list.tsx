"use client";

import {File, FileSpreadsheet, FileText, MoreHorizontal, Trash2} from "lucide-react";
import Link from "next/link";
import {StatusBadge} from "@/components/status-badge";
import type {Document, Project} from "@/lib/types";
import {relativeTime} from "@/lib/utils";

function DocumentIcon({extension}: {extension: string | null}) {
  const Icon = extension === ".csv" || extension === ".xlsx" ? FileSpreadsheet : extension === ".txt" || extension === ".docx" ? FileText : File;
  return <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-blue-400/10 text-blue-300"><Icon className="size-4" /></span>;
}

export function DocumentList({items, project, onDelete}: {items: Document[]; project?: Project; onDelete?: (document: Document) => void}) {
  return <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-[var(--surface)]">
    <div className="hidden grid-cols-[minmax(220px,2fr)_1fr_1fr_1fr_auto] gap-4 border-b border-white/[0.08] px-4 py-2.5 text-[9px] font-semibold uppercase tracking-[.12em] text-[#5f5952] md:grid"><span>Document</span><span>Source</span><span>Status</span><span>Updated</span><span>Actions</span></div>
    <div className="divide-y divide-white/[0.07]">{items.map((document) => <article key={document.document_id} className="grid gap-3 p-4 md:grid-cols-[minmax(220px,2fr)_1fr_1fr_1fr_auto] md:items-center md:gap-4">
      <Link href={`/projects/${document.project_id}/documents/${document.document_id}`} className="flex min-w-0 items-center gap-3 group"><DocumentIcon extension={document.extension} /><span className="min-w-0"><span className="block truncate text-xs font-medium group-hover:text-[var(--accent-hover)]">{document.filename ?? "Untitled document"}</span><span className="mono mt-0.5 block truncate text-[8px] text-[#5f5952]">{document.document_id}</span>{project ? null : <span className="mt-0.5 block truncate text-[9px] text-[#8f877f]">Project: {(document as Document & {project?: Project}).project?.name ?? "Unknown"}</span>}</span></Link>
      <span className="text-[10px] capitalize text-[#aaa39a]">{document.source_type ?? "unknown"}</span><StatusBadge status={document.status} /><span className="text-[10px] text-[#8f877f]">{relativeTime(document.updated_at)}</span>
      <div className="flex items-center gap-1"><Link href={`/projects/${document.project_id}/documents/${document.document_id}`} className="icon-button" aria-label={`Open ${document.filename}`}><MoreHorizontal className="size-4" /></Link>{onDelete ? <button className="icon-button text-red-300" onClick={() => onDelete(document)} aria-label={`Delete ${document.filename}`}><Trash2 className="size-4" /></button> : null}</div>
    </article>)}</div>
  </div>;
}
