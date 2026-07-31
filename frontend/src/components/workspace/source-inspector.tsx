"use client";

import {
  Box,
  Check,
  Copy,
  History,
  FileSearch,
  FileText,
  Focus,
  Network,
  X,
} from "lucide-react";
import {useQuery} from "@tanstack/react-query";
import {toast} from "sonner";
import type {DocumentVersion, RetrievalTrace} from "@/lib/types";
import {apiFetch} from "@/lib/api";
import {StatusBadge} from "@/components/status-badge";
import {relativeTime} from "@/lib/utils";
import {cn} from "@/lib/utils";
import type {WorkspaceDocument} from "@/components/workspace/workspace-data";

export type InspectorTab = "Content" | "Versions" | "Knowledge Graph" | "Retrieval Trace" | "Metadata";

function EmptyInspectorState({icon: Icon, title, description}: {
  icon: typeof FileText;
  title: string;
  description: string;
}) {
  return <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-8 text-center">
    <div className="flex size-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.025] text-[#77716a]"><Icon className="size-4.5" /></div>
    <h3 className="mt-3 text-[11px] font-medium text-[#f4efe7]">{title}</h3>
    <p className="mt-1.5 max-w-xs text-[9px] leading-4 text-[#77716a]">{description}</p>
  </div>;
}

function ContentView({document, citation}: {document: WorkspaceDocument; citation?: RetrievalTrace}) {
  if (!citation?.text) {
    return <EmptyInspectorState
      icon={FileSearch}
      title="No document preview available"
      description={`RAGForge has not returned extracted content for ${document.filename ?? "this document"}. Select a citation after a completed query to inspect its retrieved text.`}
    />;
  }

  return <div className="min-h-0 flex-1 overflow-y-auto bg-[var(--background)] p-4">
    <article className="mx-auto max-w-xl rounded-lg border border-white/[0.08] bg-[var(--surface-muted)] p-4">
      <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
        <div><p className="text-[8px] font-semibold uppercase tracking-widest text-[var(--accent)]">Retrieved source</p><h3 className="mt-1 text-[11px] font-medium">{citation.section_title || `Chunk ${citation.chunk_index ?? "—"}`}</h3></div>
        <span className="font-mono text-[8px] text-[#77716a]">Page {citation.page_start ?? "—"}</span>
      </div>
      <p className="mt-4 rounded-lg border border-[var(--accent-border)] bg-[var(--accent-soft)] p-3 text-[10px] leading-5 text-[#f4efe7] citation-highlight">{citation.text}</p>
      <div className="mt-3 flex items-center justify-between text-[8px] text-[#77716a]"><span>Chunk {citation.chunk_index ?? "—"}</span><button onClick={() => {navigator.clipboard?.writeText(citation.text ?? ""); toast.success("Source text copied");}} className="flex items-center gap-1 hover:text-white"><Copy className="size-2.5" />Copy text</button></div>
    </article>
  </div>;
}

function RetrievalView({selected}: {selected?: RetrievalTrace}) {
  if (!selected) return <EmptyInspectorState icon={Focus} title="No retrieval trace selected" description="Run a query and open one of its citations to inspect the real retrieval scores and supporting text." />;
  return <div className="min-h-0 flex-1 overflow-y-auto p-3">
    <div className="grid grid-cols-3 gap-1.5">{[
      [selected.qdrant_score?.toFixed(3) ?? "—", "Qdrant score"],
      [selected.rerank_score?.toFixed(3) ?? "—", "Rerank score"],
      [selected.retrieval_strategy ?? "—", "Strategy"],
    ].map(([value,label]) => <div key={label} className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-2"><b className="block truncate text-[10px] text-[#f4efe7]">{value}</b><span className="text-[7px] text-[#77716a]">{label}</span></div>)}</div>
    <article className="mt-3 rounded-lg border border-[var(--accent-border)] bg-[var(--surface-muted)]">
      <div className="flex items-center gap-2 p-3"><span className="flex size-5 items-center justify-center rounded bg-white/[0.05] font-mono text-[8px] text-[#aaa39a]">{selected.rank}</span><span className="min-w-0 flex-1"><span className="block truncate text-[9px] font-medium">{selected.document_name ?? "Document"}</span><span className="text-[7px] text-[#77716a]">Page {selected.page_start ?? "—"} · Chunk {selected.chunk_index ?? "—"}</span></span><span className={cn("flex size-4 items-center justify-center rounded-full", selected.used_in_answer ? "bg-[var(--accent)] text-[var(--ink-inverse)]" : "bg-white/[0.06] text-[#5f5952]")}>{selected.used_in_answer ? <Check className="size-2.5" /> : <X className="size-2.5" />}</span></div>
      <div className="border-t border-white/[0.07] px-3 py-3"><p className="text-[9px] leading-5 text-[#b7b0a7]">{selected.text || "The retrieved chunk text is unavailable."}</p></div>
    </article>
  </div>;
}

function MetadataView({document}: {document: WorkspaceDocument}) {
  const fields = [
    ["Document ID", document.document_id],
    ["Version ID", document.current_version_id ?? "—"],
    ["Project ID", document.project_id],
    ["Source type", document.source_type ?? "—"],
    ["MIME type", document.mime_type ?? "—"],
    ["Extension", document.extension ?? "—"],
    ["Status", document.status],
    ["Created by", document.created_by],
    ["Created", document.created_at],
    ["Last updated", document.updated_at],
  ];
  return <div className="min-h-0 flex-1 overflow-y-auto p-3"><div className="divide-y divide-white/[0.07] rounded-lg border border-white/[0.08]">{fields.map(([label,value]) => <div key={label} className="flex items-center gap-2 px-3 py-2"><span className="w-20 shrink-0 text-[8px] text-[#77716a]">{label}</span><code className="min-w-0 flex-1 truncate font-mono text-[8px] text-[#b7b0a7]">{value}</code><button onClick={() => {navigator.clipboard?.writeText(value); toast.success(`${label} copied`);}} className="text-[#5f5952] hover:text-white"><Copy className="size-2.5" /></button></div>)}</div></div>;
}

function VersionsView({document}: {document: WorkspaceDocument}) {
  const versions = useQuery({queryKey: ["document-versions", document.document_id], queryFn: () => apiFetch<DocumentVersion[]>(`/documents/${document.document_id}/versions`)});
  if (versions.isLoading) return <div className="space-y-2 p-3" aria-label="Loading versions">{[1,2,3].map((value) => <div key={value} className="h-20 animate-pulse rounded-lg bg-white/[0.025]" />)}</div>;
  if (versions.isError) return <EmptyInspectorState icon={History} title="Version history unavailable" description="The document version endpoint could not be loaded. Try again from the document details page." />;
  if (!versions.data?.length) return <EmptyInspectorState icon={History} title="No versions available" description="A version will appear after a source has been landed by the ingestion API." />;
  return <ol className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">{versions.data.map((version) => <li key={version.document_version_id} className="rounded-lg border border-white/[0.08] bg-white/[0.018] p-3"><div className="flex items-center justify-between gap-2"><span className="text-[10px] font-medium">Version {version.version_number}</span><StatusBadge status={version.status} /></div><p className="mt-2 text-[8px] text-[#77716a]">{relativeTime(version.created_at)} · {version.chunker_id ?? "chunker unavailable"}</p><p className="mono mt-2 truncate text-[7px] text-[#5f5952]" title={version.content_hash}>{version.content_hash}</p>{version.error_message ? <p className="mt-2 rounded bg-red-400/[0.05] p-2 text-[8px] text-red-200">{version.error_message}</p> : null}</li>)}</ol>;
}

export function SourceInspector({document, citation, activeTab, onTabChange, onClose}: {
  document: WorkspaceDocument;
  citation?: RetrievalTrace;
  activeTab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
  onClose?: () => void;
}) {
  const tabs: {label: InspectorTab; icon: typeof FileText}[] = [{label:"Content",icon:FileText},{label:"Versions",icon:History},{label:"Knowledge Graph",icon:Network},{label:"Retrieval Trace",icon:Focus},{label:"Metadata",icon:Box}];
  return <section className="flex h-full min-w-0 flex-col bg-[var(--surface)]">
    <div className="flex h-[49px] shrink-0 items-center justify-between border-b border-white/[0.08] px-3"><div className="flex min-w-0 items-center gap-2"><span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-red-400/10 text-red-300"><FileText className="size-3.5" /></span><div className="min-w-0"><h2 className="truncate text-[10px] font-medium">{document.filename ?? "Untitled document"}</h2><p className="mt-0.5 text-[8px] text-[#77716a]">{document.extension?.replace(".", "").toUpperCase() || document.source_type || "Document"}<span className="ml-1 capitalize text-[var(--accent)]">● {document.status}</span></p></div></div><div className="flex items-center">{onClose ? <button onClick={onClose} className="flex h-7 items-center gap-1 rounded-lg border border-white/[0.08] px-2 text-xs text-[var(--ink-muted)] hover:bg-white/5 hover:text-white" aria-label="Back to Assistant">Back to Assistant<X className="size-3" /></button> : null}</div></div>
    <div className="flex h-9 shrink-0 items-end gap-0.5 overflow-x-auto border-b border-white/[0.08] px-2">{tabs.map(({label,icon:Icon}) => <button key={label} onClick={() => onTabChange(label)} className={cn("flex h-9 shrink-0 items-center gap-1 px-2 text-[8px]", activeTab === label ? "border-b border-[var(--accent)] text-[var(--accent-hover)]" : "text-[#77716a] hover:text-[#b7b0a7]")}><Icon className="size-2.5" />{label}</button>)}</div>
    {activeTab === "Content" ? <ContentView document={document} citation={citation} /> : activeTab === "Versions" ? <VersionsView document={document} /> : activeTab === "Knowledge Graph" ? <EmptyInspectorState icon={Network} title="Knowledge graph unavailable" description="The current backend has no knowledge-graph endpoint, so no graph data is synthesized here." /> : activeTab === "Retrieval Trace" ? <RetrievalView selected={citation} /> : <MetadataView document={document} />}
  </section>;
}
