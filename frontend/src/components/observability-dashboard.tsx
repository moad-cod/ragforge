"use client";

import {useQuery} from "@tanstack/react-query";
import {Activity, CheckCircle2, Clock3, Database, Gauge, History, Workflow} from "lucide-react";
import Link from "next/link";
import {MetricCard} from "@/components/metric-card";
import {PageHeader} from "@/components/page-header";
import {StatusBadge} from "@/components/status-badge";
import {ErrorState} from "@/components/ui/error-state";
import {LoadingState} from "@/components/ui/loading-state";
import {useWorkspaceOverview} from "@/hooks/use-workspace-overview";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun, Project, QueryHistoryItem} from "@/lib/types";
import {formatLatency, relativeTime} from "@/lib/utils";

export function ObservabilityDashboard({projectId}: {projectId?: string}) {
  const overview = useWorkspaceOverview({documents: true, runs: true, history: true});
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`), enabled: Boolean(projectId)});
  const documents = useQuery({queryKey: ["documents", projectId], queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`), enabled: Boolean(projectId)});
  const runs = useQuery({queryKey: ["ingestion-runs", projectId], queryFn: () => apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${projectId}&limit=100`), enabled: Boolean(projectId)});
  const history = useQuery({queryKey: ["query-history", projectId], queryFn: () => apiFetch<QueryHistoryItem[]>(`/rag/projects/${projectId}/history?limit=100`), enabled: Boolean(projectId)});
  const docs = projectId ? documents.data ?? [] : overview.documents;
  const runItems = projectId ? runs.data ?? [] : overview.runs;
  const queries = projectId ? history.data ?? [] : overview.history;
  const loading = projectId ? documents.isLoading || runs.isLoading || history.isLoading : overview.pending;
  const error = projectId ? documents.isError || runs.isError || history.isError : overview.error;
  const answered = queries.filter((item) => item.answer).length;
  const cached = queries.filter((item) => item.cache_hit).length;
  const latencies = queries.map((item) => item.latency_ms).filter((value): value is number => value !== null);
  const averageLatency = latencies.length ? Math.round(latencies.reduce((total, value) => total + value, 0) / latencies.length) : null;
  const indexed = docs.filter((document) => document.status === "indexed").length;
  const failedRuns = runItems.filter((run) => run.status === "failed").length;
  if (loading) return <LoadingState label="Loading observability data" rows={6} />;
  if (error) return <ErrorState title="Observability data could not be loaded" description="One or more durable control-plane endpoints returned an error." onRetry={() => projectId ? void Promise.all([documents.refetch(), runs.refetch(), history.refetch()]) : void overview.refetch()} />;
  return <div className="mx-auto max-w-7xl space-y-6"><PageHeader eyebrow={project.data?.name ?? "Control plane"} title="Observability" description="Real metrics derived from PostgreSQL document, ingestion, and query records. No estimated or synthetic values are shown." />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Indexed documents" value={`${indexed}/${docs.length}`} detail="Current document status" icon={Database} /><MetricCard label="Successful queries" value={queries.length ? `${Math.round(answered / queries.length * 100)}%` : "—"} detail={`${answered} of ${queries.length} persisted answers`} icon={CheckCircle2} /><MetricCard label="Average latency" value={formatLatency(averageLatency)} detail={`${latencies.length} measured queries`} icon={Gauge} /><MetricCard label="Cache hit rate" value={queries.length ? `${Math.round(cached / queries.length * 100)}%` : "—"} detail={`${cached} cached responses`} icon={Activity} /></div>
    <div className="grid gap-5 xl:grid-cols-2"><section className="rounded-xl border border-white/[0.08] bg-[var(--surface)]"><div className="flex items-center justify-between border-b border-white/[0.08] p-4"><div><h2 className="text-sm font-semibold">Recent ingestion</h2><p className="mt-1 text-[9px] text-[#77716a]">{failedRuns} failed runs in the loaded window</p></div><Workflow className="size-4 text-[#5f5952]" /></div><div className="divide-y divide-white/[0.07]">{runItems.slice(0,6).map((run) => {const targetProject = projectId ?? (run as IngestionRun & {project?: Project}).project?.project_id; return <Link key={run.ingestion_run_id} href={`/projects/${targetProject}/runs/${run.ingestion_run_id}`} className="flex items-center gap-3 p-4 hover:bg-white/[0.02]"><span className="min-w-0 flex-1"><span className="mono block truncate text-[9px] text-[#b7b0a7]">{run.ingestion_run_id}</span><span className="mt-1 block text-[8px] text-[#5f5952]">{relativeTime(run.created_at)}</span></span><StatusBadge status={run.status} /></Link>;})}{!runItems.length ? <p className="p-8 text-center text-[10px] text-[#77716a]">No ingestion runs yet.</p> : null}</div></section>
      <section className="rounded-xl border border-white/[0.08] bg-[var(--surface)]"><div className="flex items-center justify-between border-b border-white/[0.08] p-4"><div><h2 className="text-sm font-semibold">Recent queries</h2><p className="mt-1 text-[9px] text-[#77716a]">Durable provider and latency records</p></div><History className="size-4 text-[#5f5952]" /></div><div className="divide-y divide-white/[0.07]">{queries.slice(0,6).map((query) => {const targetProject = projectId ?? (query as QueryHistoryItem & {project?: Project}).project?.project_id; return <Link key={query.query_log_id} href={`/projects/${targetProject}/history/${query.query_log_id}`} className="flex items-center gap-3 p-4 hover:bg-white/[0.02]"><span className="min-w-0 flex-1"><span className="block truncate text-[10px] font-medium">{query.question}</span><span className="mt-1 flex items-center gap-1 text-[8px] text-[#5f5952]"><Clock3 className="size-2.5" />{formatLatency(query.latency_ms)} · {query.provider ?? "provider unavailable"}</span></span><StatusBadge status={query.answer ? "answered" : "failed"} /></Link>;})}{!queries.length ? <p className="p-8 text-center text-[10px] text-[#77716a]">No query history yet.</p> : null}</div></section></div>
  </div>;
}
