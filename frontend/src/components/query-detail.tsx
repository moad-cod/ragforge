"use client";

import {useQuery} from "@tanstack/react-query";
import {ArrowLeft, Clock3, Copy, FileSearch} from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {toast} from "sonner";
import {PageHeader} from "@/components/page-header";
import {RetrievalTrace} from "@/components/retrieval-trace";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {ErrorState} from "@/components/ui/error-state";
import {LoadingState} from "@/components/ui/loading-state";
import {apiFetch} from "@/lib/api";
import type {Project, QueryTrace} from "@/lib/types";
import {formatLatency} from "@/lib/utils";

export function QueryDetail({projectId, queryId}: {projectId: string; queryId: string}) {
  const trace = useQuery({queryKey: ["query-trace", queryId], queryFn: () => apiFetch<QueryTrace>(`/rag/queries/${queryId}`)});
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`)});
  if (trace.isLoading) return <LoadingState label="Loading query trace" rows={6} />;
  if (trace.isError || !trace.data) return <ErrorState title="Query trace could not be loaded" description="The query may belong to another user or may no longer exist." onRetry={() => void trace.refetch()} />;
  const item = trace.data;
  return <div className="mx-auto max-w-6xl space-y-6"><Link href={`/projects/${projectId}/playground?view=history`} className="inline-flex items-center gap-1.5 text-[10px] text-[#71847b] hover:text-white"><ArrowLeft className="size-3" />Playground history</Link><PageHeader eyebrow={project.data?.name ?? "Project"} title="Query detail" description="Inspect the persisted playground answer and every ranked retrieval record used to produce it." actions={item.answer ? <Button variant="secondary" size="sm" onClick={() => {void navigator.clipboard?.writeText(item.answer ?? ""); toast.success("Answer copied");}}><Copy className="size-3.5" />Copy answer</Button> : undefined} />
    <section className="rounded-xl border border-white/[0.08] bg-[var(--surface)] p-5"><p className="text-[9px] font-semibold uppercase tracking-[.13em] text-[#53625b]">Question</p><h2 className="mt-2 text-base font-semibold leading-7">{item.question}</h2><div className="mt-4 flex flex-wrap gap-2">{item.provider ? <Badge tone="info">{item.provider}</Badge> : null}{item.model ? <Badge>{item.model}</Badge> : null}{item.cache_hit ? <Badge tone="success">cache hit</Badge> : <Badge>generated</Badge>}<Badge><Clock3 className="mr-1 size-3" />{formatLatency(item.latency_ms)}</Badge></div></section>
    <section className="rounded-xl border border-white/[0.08] bg-[var(--surface)] p-5"><p className="text-[9px] font-semibold uppercase tracking-[.13em] text-[#53625b]">Persisted answer</p>{item.answer ? <div className="markdown-answer mt-4"><ReactMarkdown remarkPlugins={[remarkGfm]}>{item.answer}</ReactMarkdown></div> : <div className="mt-4 rounded-lg bg-red-400/[0.05] p-4 text-xs text-red-200">The provider failed before an answer was persisted.</div>}</section>
    <section><div className="mb-4 flex items-center justify-between"><div><h2 className="text-sm font-semibold">Retrieval trace</h2><p className="mt-1 text-[10px] text-[#64736d]">{item.retrievals.length} ranked evidence records</p></div><FileSearch className="size-4 text-[#53625b]" /></div><RetrievalTrace items={item.retrievals} onSelect={(source) => {if (source.document_id) window.location.assign(`/projects/${projectId}/documents/${source.document_id}?chunk=${source.chunk_id ?? ""}`);}} /></section>
  </div>;
}
