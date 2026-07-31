"use client";

import {useQuery} from "@tanstack/react-query";
import {Search, Workflow} from "lucide-react";
import Link from "next/link";
import {useMemo, useState} from "react";
import {PageHeader} from "@/components/page-header";
import {StatusBadge} from "@/components/status-badge";
import {EmptyState} from "@/components/ui/empty-state";
import {ErrorState} from "@/components/ui/error-state";
import {Input} from "@/components/ui/input";
import {LoadingState} from "@/components/ui/loading-state";
import {useWorkspaceOverview} from "@/hooks/use-workspace-overview";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun, Project} from "@/lib/types";
import {relativeTime} from "@/lib/utils";

export function IngestionRunsPage({projectId}: {projectId?: string}) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const overview = useWorkspaceOverview({documents: true, runs: true});
  const projectQuery = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`), enabled: Boolean(projectId)});
  const projectRuns = useQuery({queryKey: ["ingestion-runs", projectId], queryFn: () => apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${projectId}&limit=100`), enabled: Boolean(projectId)});
  const projectDocuments = useQuery({queryKey: ["documents", projectId], queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`), enabled: Boolean(projectId)});
  const runs = projectId ? (projectRuns.data ?? []).map((run) => ({...run, project: projectQuery.data})) : overview.runs;
  const documents = useMemo(() => projectId ? projectDocuments.data ?? [] : overview.documents, [overview.documents, projectDocuments.data, projectId]);
  const documentMap = useMemo(() => new Map(documents.map((document) => [document.document_id, document])), [documents]);
  const loading = projectId ? projectRuns.isLoading || projectDocuments.isLoading : overview.pending;
  const error = projectId ? projectRuns.isError || projectDocuments.isError : overview.error;
  const filtered = useMemo(() => runs.filter((run) => {const document = documentMap.get(run.document_id); return (status === "all" || run.status === status) && `${document?.filename ?? ""} ${run.ingestion_run_id}`.toLowerCase().includes(search.toLowerCase());}), [documentMap, runs, search, status]);
  return <div className="mx-auto max-w-7xl space-y-6"><PageHeader eyebrow={projectQuery.data?.name ?? "Monitor"} title="Runs" description="Track durable pipeline execution from upload through Bronze, Silver, Gold, and Qdrant indexing." />
    <div className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-[var(--surface)] p-3 sm:flex-row"><label className="relative flex-1"><span className="sr-only">Search ingestion runs</span><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#77716a]" /><Input className="pl-9" placeholder="Search by document or run ID" value={search} onChange={(event) => setSearch(event.target.value)} /></label><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-lg border border-white/[0.08] bg-[var(--surface-muted)] px-3 text-xs outline-none" aria-label="Filter by status"><option value="all">All statuses</option>{["landed","queued","running","silver_completed","gold_completed","indexed","failed","cancelled"].map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></div>
    {loading ? <LoadingState label="Loading runs" rows={5} /> : error ? <ErrorState title="Runs could not be loaded" description="One or more project run endpoints returned an error." onRetry={() => projectId ? void Promise.all([projectRuns.refetch(), projectDocuments.refetch()]) : void overview.refetch()} /> : filtered.length ? <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-[var(--surface)]"><div className="divide-y divide-white/[0.07]">{filtered.map((run) => {const document = documentMap.get(run.document_id); const targetProjectId = projectId ?? (run as IngestionRun & {project?: Project}).project?.project_id; return <Link key={run.ingestion_run_id} href={`/projects/${targetProjectId}/runs/${run.ingestion_run_id}`} className="grid gap-3 p-4 hover:bg-white/[0.02] sm:grid-cols-[minmax(220px,2fr)_1fr_1fr_auto] sm:items-center"><span className="min-w-0"><span className="block truncate text-xs font-medium">{document?.filename ?? "Unknown source"}</span><span className="mono mt-1 block truncate text-[8px] text-[#5f5952]">{run.ingestion_run_id}</span></span><StatusBadge status={run.status} /><span className="text-[10px] text-[#8f877f]">{relativeTime(run.created_at)}</span><span className="text-[10px] text-[var(--accent)]">Inspect →</span></Link>;})}</div></div> : <EmptyState icon={Workflow} title={search || status !== "all" ? "No matching runs" : "No runs yet"} description={search || status !== "all" ? "Try a broader search or status filter." : "Upload a source to create a durable run."} />}
  </div>;
}
