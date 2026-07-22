"use client";

import {useQuery} from "@tanstack/react-query";
import {CheckCircle2, History, Search, XCircle} from "lucide-react";
import Link from "next/link";
import {useMemo, useState} from "react";
import {PageHeader} from "@/components/page-header";
import {EmptyState} from "@/components/ui/empty-state";
import {ErrorState} from "@/components/ui/error-state";
import {Input} from "@/components/ui/input";
import {LoadingState} from "@/components/ui/loading-state";
import {useWorkspaceOverview} from "@/hooks/use-workspace-overview";
import {apiFetch} from "@/lib/api";
import type {Project, QueryHistoryItem} from "@/lib/types";
import {formatLatency, relativeTime} from "@/lib/utils";

export function QueryHistoryPage({projectId}: {projectId?: string}) {
  const [search, setSearch] = useState("");
  const [outcome, setOutcome] = useState("all");
  const overview = useWorkspaceOverview({documents: false, history: true});
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`), enabled: Boolean(projectId)});
  const history = useQuery({queryKey: ["query-history", projectId], queryFn: () => apiFetch<QueryHistoryItem[]>(`/rag/projects/${projectId}/history?limit=100`), enabled: Boolean(projectId)});
  const items = projectId ? (history.data ?? []).map((item) => ({...item, project: project.data})) : overview.history;
  const loading = projectId ? history.isLoading : overview.pending;
  const error = projectId ? history.isError : overview.error;
  const filtered = useMemo(() => items.filter((item) => (outcome === "all" || (outcome === "answered" ? Boolean(item.answer) : !item.answer)) && `${item.question} ${item.answer ?? ""}`.toLowerCase().includes(search.toLowerCase())), [items, outcome, search]);
  return <div className="mx-auto max-w-7xl space-y-6"><PageHeader eyebrow={project.data?.name ?? "Observability"} title="Query history" description="Review durable questions and answers, provider metadata, latency, cache behavior, and retrieval evidence." />
    <div className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-[#0a1511] p-3 sm:flex-row"><label className="relative flex-1"><span className="sr-only">Search query history</span><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#64736d]" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search questions and answers" /></label><select value={outcome} onChange={(event) => setOutcome(event.target.value)} className="h-10 rounded-lg border border-white/[0.08] bg-[var(--surface-muted)] px-3 text-xs" aria-label="Filter query outcome"><option value="all">All outcomes</option><option value="answered">Answered</option><option value="failed">No answer</option></select></div>
    {loading ? <LoadingState label="Loading query history" rows={6} /> : error ? <ErrorState title="Query history could not be loaded" description="The durable query log endpoint returned an error." onRetry={() => projectId ? void history.refetch() : void overview.refetch()} /> : filtered.length ? <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-[#0a1511]"><div className="divide-y divide-white/[0.07]">{filtered.map((item) => {const itemProjectId = projectId ?? (item as QueryHistoryItem & {project?: Project}).project?.project_id; return <Link key={item.query_log_id} href={`/projects/${itemProjectId}/history/${item.query_log_id}`} className="grid gap-3 p-4 hover:bg-white/[0.02] md:grid-cols-[minmax(260px,2fr)_1fr_1fr_auto] md:items-center"><span className="min-w-0"><span className="block line-clamp-2 text-xs font-medium leading-5">{item.question}</span><span className="mt-1 block line-clamp-1 text-[9px] text-[#64736d]">{item.answer ?? "No answer was persisted"}</span></span><span className="flex items-center gap-2 text-[10px] text-[#83948c]">{item.answer ? <CheckCircle2 className="size-3.5 text-emerald-300" /> : <XCircle className="size-3.5 text-red-300" />}{item.answer ? "Answered" : "Failed"}</span><span className="text-[10px] text-[#71847b]">{formatLatency(item.latency_ms)} · {item.cache_hit ? "cached" : "generated"}</span><span className="text-[9px] text-[#53625b]">{relativeTime(item.created_at)}</span></Link>;})}</div></div> : <EmptyState icon={History} title={search || outcome !== "all" ? "No matching queries" : "No query history yet"} description={search || outcome !== "all" ? "Try a broader search or outcome filter." : "Questions will appear after you use a project workspace chat."} />}
  </div>;
}
