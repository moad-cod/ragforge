"use client";

import {useMutation, useQueryClient} from "@tanstack/react-query";
import {
  Check,
  Circle,
  LoaderCircle,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import {useEffect, useState} from "react";
import {toast} from "sonner";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun, IngestionStatus} from "@/lib/types";
import {cn} from "@/lib/utils";
import {useIngestionStream} from "@/hooks/use-ingestion-stream";

const STEPS: {status: IngestionStatus; label: string}[] = [
  {status: "landed", label: "Original saved"},
  {status: "queued", label: "Queued"},
  {status: "running", label: "Extracting content"},
  {status: "silver_completed", label: "Chunks created"},
  {status: "gold_completed", label: "Embeddings ready"},
  {status: "indexed", label: "Search index ready"},
];
const RANK = Object.fromEntries(
  STEPS.map((step, index) => [step.status, index]),
) as Record<string, number>;

export function IngestionCard({
  initialRun,
  document,
  projectId,
}: {
  initialRun: IngestionRun;
  document?: Document;
  projectId: string;
}) {
  const queryClient = useQueryClient();
  const {run, connected} = useIngestionStream(initialRun);
  const [now, setNow] = useState(() => Date.now());
  const currentRank = RANK[run.status] ?? 0;
  const failed = run.status === "failed" || run.status === "cancelled";
  useEffect(() => {
    if (run.finished_at) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [run.finished_at]);
  const elapsedStart = new Date(run.started_at ?? run.created_at).getTime();
  const elapsedEnd = run.finished_at ? new Date(run.finished_at).getTime() : now;
  const elapsedSeconds = Math.max(0, Math.floor((elapsedEnd - elapsedStart) / 1000));
  const retry = useMutation({
    mutationFn: () =>
      apiFetch<IngestionRun>(`/ingest/runs/${run.ingestion_run_id}/retry`, {
        method: "POST",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({queryKey: ["ingestion-runs", projectId]});
      toast.success("Ingestion retry queued");
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Unable to retry ingestion"),
  });

  return (
    <div
      className={cn(
        "rounded-2xl border bg-white p-5",
        failed ? "border-red-200" : "border-[var(--border)]",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="max-w-md truncate text-sm font-semibold">
              {document?.filename ?? "Document ingestion"}
            </h3>
            {!failed && run.status !== "indexed" ? (
              <span
                className={cn(
                  "size-2 rounded-full",
                  connected ? "bg-emerald-500" : "bg-amber-400",
                )}
                title={connected ? "Live updates connected" : "Recovering from status"}
              />
            ) : null}
          </div>
          <p className="mt-1 font-mono text-[11px] text-[var(--ink-faint)]">
            {run.ingestion_run_id}
          </p>
        </div>
        <Badge
          tone={
            run.status === "indexed"
              ? "success"
              : failed
                ? "danger"
                : "info"
          }
        >
          {run.status.replaceAll("_", " ")}
        </Badge>
      </div>
      <p className="mt-2 text-xs text-[var(--ink-faint)]">
        Elapsed {elapsedSeconds < 60
          ? `${elapsedSeconds}s`
          : `${Math.floor(elapsedSeconds / 60)}m ${elapsedSeconds % 60}s`}
      </p>

      {failed ? (
        <div className="mt-5 rounded-xl bg-[var(--danger-soft)] p-4">
          <div className="flex gap-3">
            <TriangleAlert className="mt-0.5 size-5 shrink-0 text-[var(--danger)]" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--danger)]">
                Document processing failed
              </p>
              <p className="mt-1 text-sm leading-6 text-red-700/80">
                {run.error_message || "The ingestion pipeline could not complete."}
              </p>
              {run.status === "failed" ? (
                <Button
                  className="mt-3"
                  size="sm"
                  variant="secondary"
                  disabled={retry.isPending}
                  onClick={() => retry.mutate()}
                >
                  {retry.isPending ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <RefreshCw className="size-4" />
                  )}
                  Retry from Bronze
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {STEPS.map((step, index) => {
            const complete = run.status === "indexed" || index < currentRank;
            const active = index === currentRank && run.status !== "indexed";
            return (
              <div key={step.status} className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "flex size-6 items-center justify-center rounded-full border",
                    complete && "border-emerald-500 bg-emerald-500 text-white",
                    active &&
                      "border-indigo-300 bg-indigo-50 text-[var(--accent)]",
                    !complete &&
                      !active &&
                      "border-slate-200 bg-slate-50 text-slate-300",
                  )}
                >
                  {complete ? (
                    <Check className="size-3.5" />
                  ) : active ? (
                    <LoaderCircle className="size-3.5 animate-spin" />
                  ) : (
                    <Circle className="size-2.5" />
                  )}
                </span>
                <span
                  className={cn(
                    "text-xs font-medium",
                    complete || active
                      ? "text-[var(--ink)]"
                      : "text-[var(--ink-faint)]",
                  )}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
