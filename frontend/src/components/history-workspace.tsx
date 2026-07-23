"use client";

import {useQuery} from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  Clock3,
  FileSearch,
  History,
  Search,
  XCircle,
} from "lucide-react";
import {useState} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {PageHeader} from "@/components/page-header";
import {Badge} from "@/components/ui/badge";
import {Card} from "@/components/ui/card";
import {EmptyState} from "@/components/ui/empty-state";
import {Input} from "@/components/ui/input";
import {apiFetch} from "@/lib/api";
import type {Project, QueryHistoryItem, QueryTrace} from "@/lib/types";
import {formatLatency, relativeTime} from "@/lib/utils";

export function HistoryWorkspace({projectId}: {projectId: string}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const {data: project} = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
  });
  const {data: history = [], isLoading} = useQuery({
    queryKey: ["query-history", projectId],
    queryFn: () =>
      apiFetch<QueryHistoryItem[]>(`/rag/projects/${projectId}/history?limit=100`),
  });
  const {data: trace, isLoading: traceLoading} = useQuery({
    queryKey: ["query-trace", selectedId],
    queryFn: () => apiFetch<QueryTrace>(`/rag/queries/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const filtered = history.filter((item) =>
    `${item.question} ${item.answer ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={project?.name ?? "Project"}
        title="Query history"
        description="Inspect durable answers, model metadata, latency, cache behavior, and the evidence retrieved for each query."
      />

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <section>
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--ink-faint)]" />
            <Input
              className="pl-9"
              placeholder="Search questions and answers"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {isLoading ? (
            <div className="h-96 animate-pulse rounded-2xl bg-white" />
          ) : filtered.length ? (
            <Card className="max-h-[720px] divide-y divide-[var(--border)] overflow-y-auto">
              {filtered.map((item) => (
                <button
                  key={item.query_log_id}
                  className={`w-full p-4 text-left transition hover:bg-slate-50 ${
                    selectedId === item.query_log_id ? "bg-indigo-50/60" : ""
                  }`}
                  onClick={() => setSelectedId(item.query_log_id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-2 text-sm font-semibold leading-5">
                      {item.question}
                    </p>
                    {item.answer ? (
                      <CheckCircle2 className="size-4 shrink-0 text-[var(--success)]" />
                    ) : (
                      <XCircle className="size-4 shrink-0 text-red-500" />
                    )}
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-[var(--ink-muted)]">
                    {item.answer || "This query did not produce a completed answer."}
                  </p>
                  <div className="mt-3 flex items-center gap-2 text-[10px] text-[var(--ink-faint)]">
                    <span>{relativeTime(item.created_at)}</span>
                    <span>·</span>
                    <span>{formatLatency(item.latency_ms)}</span>
                    {item.cache_hit ? (
                      <>
                        <span>·</span>
                        <span className="text-[var(--success)]">cached</span>
                      </>
                    ) : null}
                  </div>
                </button>
              ))}
            </Card>
          ) : (
            <EmptyState
              icon={History}
              title={search ? "No matching queries" : "No query history yet"}
              description={
                search
                  ? "Try a different search phrase."
                  : "Completed and failed questions will appear here after you use the project chat."
              }
            />
          )}
        </section>

        <section>
          {!selectedId ? (
            <Card className="flex min-h-[520px] flex-col items-center justify-center p-8 text-center">
              <div className="flex size-12 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent)]">
                <FileSearch className="size-6" />
              </div>
              <h2 className="mt-4 font-semibold">Select a query</h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--ink-muted)]">
                Open a history item to inspect its answer and ranked retrieval evidence.
              </p>
            </Card>
          ) : traceLoading || !trace ? (
            <div className="h-[620px] animate-pulse rounded-2xl bg-white" />
          ) : (
            <Card className="overflow-hidden">
              <div className="border-b border-[var(--border)] p-5">
                <div className="flex items-start gap-3">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                    <Bot className="size-4" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-faint)]">
                      Question
                    </p>
                    <h2 className="mt-1 text-lg font-semibold leading-7">
                      {trace.question}
                    </h2>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {trace.provider ? <Badge tone="info">{trace.provider}</Badge> : null}
                  {trace.model ? <Badge>{trace.model}</Badge> : null}
                  {trace.cache_hit ? <Badge tone="success">cache hit</Badge> : null}
                  <Badge>
                    <Clock3 className="mr-1 size-3" />
                    {formatLatency(trace.latency_ms)}
                  </Badge>
                </div>
              </div>

              <div className="p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-faint)]">
                  Persisted answer
                </p>
                {trace.answer ? (
                  <div className="markdown-answer mt-3">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {trace.answer}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="mt-3 rounded-xl bg-[var(--danger-soft)] p-4 text-sm text-[var(--danger)]">
                    The provider failed before an answer was persisted.
                  </div>
                )}
              </div>

              <div className="border-t border-[var(--border)] bg-[var(--surface-muted)] p-5">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">
                    Retrieval trace ({trace.retrievals.length})
                  </p>
                  <span className="text-xs text-[var(--ink-faint)]">
                    Ranked evidence
                  </span>
                </div>
                <div className="mt-4 space-y-3">
                  {trace.retrievals.map((retrieval) => (
                    <div
                      key={retrieval.retrieval_log_id}
                      className="rounded-xl border border-[var(--border)] bg-white p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold">
                            #{retrieval.rank} ·{" "}
                            {retrieval.document_name || "Deleted document"}
                          </p>
                          <p className="mt-1 text-[10px] text-[var(--ink-faint)]">
                            {retrieval.section_title ||
                              `Chunk ${retrieval.chunk_index ?? "unknown"}`}
                          </p>
                        </div>
                        <Badge tone={retrieval.used_in_answer ? "success" : "neutral"}>
                          {retrieval.used_in_answer ? "used" : "not used"}
                        </Badge>
                      </div>
                      <p className="mt-3 line-clamp-5 text-xs leading-5 text-[var(--ink-muted)]">
                        {retrieval.text || "Chunk content is no longer available."}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-3 border-t border-[var(--border)] pt-3 text-[10px] text-[var(--ink-faint)]">
                        <span>strategy: {retrieval.retrieval_strategy || "—"}</span>
                        <span>
                          qdrant:{" "}
                          {retrieval.qdrant_score?.toFixed(3) ?? "—"}
                        </span>
                        <span>
                          rerank:{" "}
                          {retrieval.rerank_score?.toFixed(3) ?? "—"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}
