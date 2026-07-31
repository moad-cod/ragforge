"use client";

import {useQuery} from "@tanstack/react-query";
import {ArrowLeft, Database, HardDrive, Network} from "lucide-react";
import Link from "next/link";
import {IngestionPipeline} from "@/components/ingestion-pipeline";
import {PageHeader} from "@/components/page-header";
import {ErrorState} from "@/components/ui/error-state";
import {LoadingState} from "@/components/ui/loading-state";
import {useIngestionStream} from "@/hooks/use-ingestion-stream";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun, Project} from "@/lib/types";

function LiveRun({initial, document, projectId}: {initial: IngestionRun; document?: Document; projectId: string}) {const {run, connected} = useIngestionStream(initial); return <><div className="mb-4 flex items-center gap-2 text-[10px] text-[#8f877f]"><span className={`size-2 rounded-full ${connected ? "bg-[var(--accent)]" : "bg-amber-400"}`} />{connected ? "Live pipeline updates connected" : "Recovering from durable status"}</div><IngestionPipeline run={run} document={document} projectId={projectId} /><div className="mt-5 grid gap-3 sm:grid-cols-3">{[[HardDrive,"Bronze artifact",run.progress.bronze],[Database,"Silver / Gold",run.progress.silver && run.progress.gold],[Network,"Qdrant index",run.progress.qdrant]].map(([Icon,label,ready]) => {const Component = Icon as typeof HardDrive; return <div key={String(label)} className="rounded-xl border border-white/[0.08] bg-[var(--surface)] p-4"><Component className={`size-4 ${ready ? "text-[var(--accent)]" : "text-[#5f5952]"}`} /><p className="mt-3 text-xs font-medium">{String(label)}</p><p className="mt-1 text-[9px] text-[#77716a]">{ready ? "Durable boundary completed" : "Not completed"}</p></div>;})}</div></>;}

export function IngestionRunDetail({projectId, runId}: {projectId: string; runId: string}) {
  const run = useQuery({queryKey: ["ingestion-run", runId], queryFn: () => apiFetch<IngestionRun>(`/ingest/runs/${runId}`)});
  const document = useQuery({queryKey: ["document", run.data?.document_id], queryFn: () => apiFetch<Document>(`/documents/${run.data?.document_id}`), enabled: Boolean(run.data?.document_id)});
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`)});
  return <div className="mx-auto max-w-6xl space-y-6"><Link href={`/projects/${projectId}/pipelines`} className="inline-flex items-center gap-1.5 text-[10px] text-[#8f877f] hover:text-white"><ArrowLeft className="size-3" />All runs</Link><PageHeader eyebrow={project.data?.name ?? "Project"} title="Run details" description="Inspect stage progress, durable boundaries, diagnostics, and retry state for this pipeline execution." />{run.isLoading ? <LoadingState label="Loading run" rows={4} /> : run.isError || !run.data ? <ErrorState title="Run could not be loaded" description="The run may not exist or may belong to another project." onRetry={() => void run.refetch()} /> : <LiveRun key={`${run.data.ingestion_run_id}:${run.data.status}`} initial={run.data} document={document.data} projectId={projectId} />}</div>;
}
