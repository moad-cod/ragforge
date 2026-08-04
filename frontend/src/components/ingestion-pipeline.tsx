"use client";

import {Check, Circle, Copy, LoaderCircle, RefreshCw, TriangleAlert} from "lucide-react";
import {useMutation, useQueryClient} from "@tanstack/react-query";
import Link from "next/link";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {StatusBadge} from "@/components/status-badge";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun} from "@/lib/types";
import {cn, relativeTime} from "@/lib/utils";

const stages = [
  {label: "Uploaded", complete: (run: IngestionRun) => Boolean(run.created_at)},
  {label: "Bronze landed", complete: (run: IngestionRun) => run.progress.bronze},
  {label: "Parsing", complete: (run: IngestionRun) => run.progress.silver},
  {label: "Chunking", complete: (run: IngestionRun) => run.progress.silver},
  {label: "Silver completed", complete: (run: IngestionRun) => run.progress.silver},
  {label: "Embedding", complete: (run: IngestionRun) => run.progress.gold},
  {label: "Gold completed", complete: (run: IngestionRun) => run.progress.gold},
  {label: "Qdrant indexing", complete: (run: IngestionRun) => run.progress.qdrant},
  {label: "Indexed", complete: (run: IngestionRun) => run.status === "indexed"},
];

export function IngestionPipeline({run, document, projectId, compact = false}: {run: IngestionRun; document?: Document; projectId: string; compact?: boolean}) {
  const queryClient = useQueryClient();
  const failed = run.status === "failed" || run.status === "cancelled";
  const completed = stages.map((stage) => stage.complete(run));
  const current = completed.findIndex((value) => !value);
  const embedding = run.embedding_progress;
  const retry = useMutation({mutationFn: () => apiFetch<IngestionRun>(`/ingest/runs/${run.ingestion_run_id}/retry`, {method: "POST"}), onSuccess: async () => {await Promise.all([queryClient.invalidateQueries({queryKey: ["ingestion-runs", projectId]}), queryClient.invalidateQueries({queryKey: ["ingestion-run", run.ingestion_run_id]})]); toast.success("Retry queued from the durable Bronze artifact");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to retry ingestion")});
  return <section className="rounded-xl border border-white/[0.08] bg-[var(--surface)] p-4" aria-live="polite">
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate text-xs font-semibold">{document?.filename ?? "Document ingestion"}</h3><p className="mono mt-1 truncate text-[8px] text-[#5f5952]">{run.ingestion_run_id}</p></div><StatusBadge status={run.status} /></div>
    <div className={cn("mt-4 grid gap-2", compact ? "grid-cols-3 sm:grid-cols-5" : "sm:grid-cols-3 lg:grid-cols-9")}>
      {stages.map((stage, index) => {const done = completed[index]; const active = !failed && current === index; return <div key={stage.label} className="relative flex items-center gap-2 lg:flex-col lg:text-center"><span className={cn("flex size-6 shrink-0 items-center justify-center rounded-full border", done ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--ink-inverse)]" : active ? "border-blue-400 bg-blue-400/10 text-blue-300" : failed && current === index ? "border-red-400 bg-red-400/10 text-red-300" : "border-white/10 text-[#403c36]")}>{done ? <Check className="size-3.5" /> : active ? <LoaderCircle className="size-3.5 animate-spin" /> : <Circle className="size-2.5" />}</span><span className={cn("text-[9px] leading-4", done ? "text-[#c9c1b7]" : active ? "text-blue-200" : "text-[#5f5952]")}>{stage.label}</span></div>;})}
    </div>
    {!compact && embedding ? <div className="mt-4 rounded-lg border border-white/[0.07] bg-white/[0.02] p-3 text-[9px] text-[#aaa39a]"><div className="flex flex-wrap items-center gap-x-4 gap-y-1"><span className="font-medium text-[#c9c1b7]">Embedding {embedding.stage.replaceAll("_", " ")}</span><span>{embedding.embedded_chunks}/{embedding.total_chunks} chunks</span>{typeof embedding.embedded_batches === "number" && typeof embedding.total_batches === "number" ? <span>{embedding.embedded_batches}/{embedding.total_batches} batches</span> : null}<span className="mono break-all">{embedding.embedding_model}</span></div><div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[#77716a]">{embedding.embedding_backend ? <span>{embedding.embedding_backend}</span> : null}{embedding.embedding_device ? <span>Device {embedding.embedding_device}</span> : null}{embedding.embedding_dimension ? <span>{embedding.embedding_dimension} dimensions</span> : null}{embedding.last_heartbeat_at ? <span>Heartbeat {relativeTime(embedding.last_heartbeat_at)}</span> : null}</div>{embedding.error_message ? <p className="mt-2 text-red-200">{embedding.error_message}</p> : null}</div> : null}
    {!compact ? <div className="mt-4 grid gap-2 border-t border-white/[0.07] pt-3 text-[9px] text-[#77716a] sm:grid-cols-3"><span>Created {relativeTime(run.created_at)}</span><span>Started {run.started_at ? relativeTime(run.started_at) : "not reported"}</span><span>Finished {run.finished_at ? relativeTime(run.finished_at) : "not yet"}</span></div> : null}
    {failed ? <div className="mt-4 rounded-lg border border-red-400/15 bg-red-400/[0.045] p-3"><div className="flex gap-2.5"><TriangleAlert className="mt-0.5 size-4 shrink-0 text-red-300" /><div className="min-w-0 flex-1"><p className="text-[11px] font-semibold text-red-200">Document processing failed</p><p className="mt-1 text-[10px] leading-5 text-red-200/70">{run.error_message || "The pipeline stopped before indexing completed."}</p><details className="mt-2"><summary className="cursor-pointer text-[9px] text-[#b7b0a7]">Technical details</summary><div className="mono mt-2 rounded-md bg-black/20 p-2 text-[8px] leading-4 text-[#aaa39a]">Run: {run.ingestion_run_id}<br />DAG: {run.airflow_dag_run_id || "not assigned"}<br />Retry reuses the landed Bronze artifact and does not create a new version.</div></details><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="secondary" disabled={retry.isPending || run.status !== "failed"} onClick={() => retry.mutate()}><RefreshCw className={cn("size-3.5", retry.isPending && "animate-spin")} />Retry from Bronze</Button><Button size="sm" variant="ghost" onClick={() => {void navigator.clipboard?.writeText(`Run: ${run.ingestion_run_id}\nStatus: ${run.status}\nDocument: ${run.document_id}\nError: ${run.error_message || "none"}`); toast.success("Diagnostics copied");}}><Copy className="size-3.5" />Copy diagnostics</Button><Link href={`/projects/${projectId}/documents/${run.document_id}`} className="flex h-9 items-center px-3 text-[10px] text-[var(--accent)] hover:text-[var(--accent-hover)]">Open document</Link></div></div></div></div> : null}
  </section>;
}
