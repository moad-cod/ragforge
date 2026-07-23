import {FileSearch} from "lucide-react";
import {StatusBadge} from "@/components/status-badge";
import type {RetrievalTrace as RetrievalTraceType} from "@/lib/types";

export function RetrievalTrace({items, onSelect}: {items: RetrievalTraceType[]; onSelect?: (item: RetrievalTraceType) => void}) {
  if (!items.length) return <div className="rounded-xl border border-dashed border-white/[0.1] p-8 text-center"><FileSearch className="mx-auto size-5 text-[#53625b]" /><p className="mt-3 text-xs font-medium">No retrieval evidence was persisted</p><p className="mt-1 text-[10px] text-[#64736d]">The query may have failed before retrieval completed.</p></div>;
  return <div className="space-y-3">{items.map((item) => <article key={item.retrieval_log_id} className="rounded-xl border border-white/[0.08] bg-[var(--surface)] p-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex items-center gap-2"><span className="mono flex size-6 items-center justify-center rounded-md bg-white/[0.05] text-[9px]">{item.rank}</span><h3 className="truncate text-xs font-semibold">{item.document_name ?? "Deleted document"}</h3></div><p className="mt-1.5 text-[9px] text-[#64736d]">{item.section_title || `Chunk ${item.chunk_index ?? "unknown"}`} · Page {item.page_start ?? "—"}</p></div><StatusBadge status={item.used_in_answer ? "used" : "not used"} /></div>
    <p className="mt-3 whitespace-pre-wrap text-[11px] leading-5 text-[#a9b7b0]">{item.text || "Chunk content is no longer available."}</p>
    <dl className="mt-4 grid gap-2 border-t border-white/[0.07] pt-3 text-[9px] sm:grid-cols-4"><div><dt className="text-[#53625b]">Qdrant score</dt><dd className="mono mt-1 text-[#a9b7b0]">{item.qdrant_score?.toFixed(4) ?? "—"}</dd></div><div><dt className="text-[#53625b]">Rerank score</dt><dd className="mono mt-1 text-[#a9b7b0]">{item.rerank_score?.toFixed(4) ?? "—"}</dd></div><div><dt className="text-[#53625b]">Strategy</dt><dd className="mt-1 text-[#a9b7b0]">{item.retrieval_strategy ?? "—"}</dd></div><div><dt className="text-[#53625b]">Version lineage</dt><dd className="mono mt-1 truncate text-[#a9b7b0]" title={item.document_version_id ?? undefined}>{item.document_version_id ?? "—"}</dd></div></dl>
    {onSelect ? <button onClick={() => onSelect(item)} className="mt-3 text-[10px] font-medium text-[var(--accent)] hover:text-[var(--accent-hover)]">Open supporting source →</button> : null}
  </article>)}</div>;
}
