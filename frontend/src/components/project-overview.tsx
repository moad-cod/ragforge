"use client";

import {useQuery} from "@tanstack/react-query";
import {ArrowRight, BarChart3, Database, FileStack, MessageSquareText, Sparkles, Workflow} from "lucide-react";
import Link from "next/link";
import {MetricCard} from "@/components/metric-card";
import {PageHeader} from "@/components/page-header";
import {StatusBadge} from "@/components/status-badge";
import {Button} from "@/components/ui/button";
import {ErrorState} from "@/components/ui/error-state";
import {LoadingState} from "@/components/ui/loading-state";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun, Project, QueryHistoryItem} from "@/lib/types";
import {formatLatency, relativeTime} from "@/lib/utils";

export function ProjectOverview({projectId}: {projectId: string}) {
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`)});
  const documents = useQuery({queryKey: ["documents", projectId], queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`)});
  const runs = useQuery({queryKey: ["ingestion-runs", projectId], queryFn: () => apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${projectId}&limit=100`)});
  const history = useQuery({queryKey: ["query-history", projectId], queryFn: () => apiFetch<QueryHistoryItem[]>(`/rag/projects/${projectId}/history?limit=100`)});
  const loading = project.isLoading || documents.isLoading || runs.isLoading || history.isLoading;
  const error = project.isError || documents.isError || runs.isError || history.isError || !project.data;
  if (loading) return <LoadingState label="Loading project overview" rows={6} />;
  if (error) return <ErrorState title="Project overview could not be loaded" description="One or more project endpoints returned an error." onRetry={() => void Promise.all([project.refetch(), documents.refetch(), runs.refetch(), history.refetch()])} />;

  const docs = documents.data ?? [];
  const runItems = runs.data ?? [];
  const queries = history.data ?? [];
  const indexed = docs.filter((document) => document.status === "indexed").length;
  const activeRuns = runItems.filter((run) => !["indexed", "failed", "cancelled"].includes(run.status));
  const failedRuns = runItems.filter((run) => run.status === "failed");
  const lastQuery = queries[0];
  const nextAction = !docs.length
    ? {label: "Add sources", href: `/projects/${projectId}/sources`, Icon: FileStack, description: "Upload files, URLs, or drive sources before running retrieval tests."}
    : indexed === 0
      ? {label: "Watch pipelines", href: `/projects/${projectId}/pipelines`, Icon: Workflow, description: "Sources exist but are not indexed yet. Track the pipeline to completion."}
      : {label: "Open playground", href: `/projects/${projectId}/playground`, Icon: MessageSquareText, description: "Ask grounded questions and inspect retrieval evidence."};
  const NextIcon = nextAction.Icon;

  return <div className="mx-auto max-w-7xl space-y-6">
    <PageHeader
      eyebrow="Project overview"
      title={project.data.name}
      description="Project-first control center for sources, playground queries, pipeline state, and the next experiment/evaluation surfaces."
      actions={<Link href={nextAction.href}><Button><ArrowRight className="size-4" />{nextAction.label}</Button></Link>}
    />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Indexed sources" value={`${indexed}/${docs.length}`} detail="Ready for retrieval" icon={Database} />
      <MetricCard label="Active runs" value={activeRuns.length} detail="Non-terminal pipeline executions" icon={Workflow} />
      <MetricCard label="Failed runs" value={failedRuns.length} detail="Retry from durable Bronze when available" icon={BarChart3} />
      <MetricCard label="Playground queries" value={queries.length} detail="Persisted in query history" icon={Sparkles} />
    </div>
    <section className="rounded-xl border border-[var(--accent-border)] bg-[var(--surface)] p-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]"><NextIcon className="size-5" /></span>
          <div>
            <p className="text-[9px] font-semibold uppercase tracking-[.14em] text-[#817a72]">Next action</p>
            <h2 className="mt-1 text-sm font-semibold">{nextAction.label}</h2>
            <p className="mt-1 text-xs leading-5 text-[var(--ink-muted)]">{nextAction.description}</p>
          </div>
        </div>
        <Link href={nextAction.href} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-[var(--accent-soft)] px-3 text-xs font-medium text-[var(--accent-hover)] hover:bg-[var(--accent-muted)]">Continue<ArrowRight className="size-3.5" /></Link>
      </div>
    </section>
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
        <div className="flex items-center justify-between border-b border-white/[0.08] p-4"><div><h2 className="text-sm font-semibold">Recent pipeline runs</h2><p className="mt-1 text-[9px] text-[#77716a]">Operational state for this project</p></div><Link href={`/projects/${projectId}/pipelines`} className="text-[10px] text-[var(--accent)]">View runs</Link></div>
        <div className="divide-y divide-white/[0.07]">{runItems.slice(0, 5).map((run) => <Link key={run.ingestion_run_id} href={`/projects/${projectId}/runs/${run.ingestion_run_id}`} className="flex items-center gap-3 p-4 hover:bg-white/[0.02]"><span className="min-w-0 flex-1"><span className="mono block truncate text-[9px] text-[#b7b0a7]">{run.ingestion_run_id}</span><span className="mt-1 block text-[8px] text-[#5f5952]">{relativeTime(run.created_at)}</span></span><StatusBadge status={run.status} /></Link>)}{!runItems.length ? <p className="p-8 text-center text-[10px] text-[#77716a]">No runs yet. Add sources to start ingestion.</p> : null}</div>
      </section>
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
        <div className="flex items-center justify-between border-b border-white/[0.08] p-4"><div><h2 className="text-sm font-semibold">Latest playground result</h2><p className="mt-1 text-[9px] text-[#77716a]">Question, latency, and answer status</p></div><Link href={`/projects/${projectId}/playground`} className="text-[10px] text-[var(--accent)]">Open playground</Link></div>
        {lastQuery ? <Link href={`/projects/${projectId}/history/${lastQuery.query_log_id}`} className="block p-4 hover:bg-white/[0.02]"><p className="line-clamp-2 text-xs font-medium leading-5">{lastQuery.question}</p><p className="mt-2 line-clamp-2 text-[10px] leading-5 text-[#8f877f]">{lastQuery.answer ?? "No answer was persisted."}</p><div className="mt-3 flex flex-wrap gap-2 text-[9px] text-[#5f5952]"><span>{formatLatency(lastQuery.latency_ms)}</span><span>{lastQuery.cache_hit ? "cached" : "generated"}</span><span>{lastQuery.model ?? "model unavailable"}</span></div></Link> : <p className="p-8 text-center text-[10px] text-[#77716a]">No playground queries yet. Ask a question after indexing sources.</p>}
      </section>
    </div>
  </div>;
}
