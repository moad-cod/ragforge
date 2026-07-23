"use client";

import {useQuery} from "@tanstack/react-query";
import {
  Bot,
  ChevronDown,
  CircleStop,
  FileSearch,
  LoaderCircle,
  Send,
  Sparkles,
  UserRound,
} from "lucide-react";
import {useMemo, useRef, useState} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {toast} from "sonner";
import {PageHeader} from "@/components/page-header";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {apiFetch} from "@/lib/api";
import {consumeSSE} from "@/lib/sse";
import type {Document, Project, QueryTrace, RetrievalTrace, StreamEvent} from "@/lib/types";
import {cn, formatLatency} from "@/lib/utils";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  stage?: string;
  complete?: boolean;
  error?: string;
  queryLogId?: string;
  provider?: string;
  model?: string;
  latencyMs?: number;
  cacheHit?: boolean;
  sources?: RetrievalTrace[];
};

const STAGE_LABELS: Record<string, string> = {
  "query.received": "Understanding your question",
  "query.embedding": "Preparing semantic search",
  "query.retrieving": "Searching relevant sections",
  "query.reranking": "Ranking the best evidence",
  "query.generating": "Generating a grounded answer",
};

export function ChatWorkspace({projectId}: {projectId: string}) {
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState<"gemini" | "groq">("gemini");
  const [documentId, setDocumentId] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const {data: project} = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
  });
  const {data: documents = []} = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`),
  });
  const indexedDocuments = useMemo(
    () => documents.filter((document) => document.status === "indexed"),
    [documents],
  );

  function updateAssistant(id: string, update: Partial<Message>) {
    setMessages((current) =>
      current.map((message) =>
        message.id === id ? {...message, ...update} : message,
      ),
    );
  }

  function appendToken(id: string, token: string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === id ? {...message, text: message.text + token} : message,
      ),
    );
  }

  async function loadTrace(assistantId: string, queryLogId: string) {
    try {
      const trace = await apiFetch<QueryTrace>(`/rag/queries/${queryLogId}`);
      updateAssistant(assistantId, {
        sources: trace.retrievals,
        provider: trace.provider ?? undefined,
        model: trace.model ?? undefined,
        latencyMs: trace.latency_ms ?? undefined,
        cacheHit: trace.cache_hit,
      });
    } catch {
      // The answer remains useful even if debug trace loading is unavailable.
    }
  }

  async function sendQuestion() {
    const value = question.trim();
    if (!value || streaming) return;
    if (!indexedDocuments.length) {
      toast.error("Index at least one document before asking a question");
      return;
    }

    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      {id: userId, role: "user", text: value, complete: true},
      {
        id: assistantId,
        role: "assistant",
        text: "",
        stage: "query.received",
      },
    ]);
    setQuestion("");
    setStreaming(true);
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const response = await fetch("/api/backend/rag/query/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          question: value,
          project_id: projectId,
          provider,
          document_id: documentId || null,
          include_context: false,
        }),
        signal: controller.signal,
      });
      await consumeSSE(response, {
        onEvent: (event: StreamEvent) => {
          if (event.event in STAGE_LABELS) {
            updateAssistant(assistantId, {stage: event.event});
          } else if (event.event === "query.token" && typeof event.text === "string") {
            appendToken(assistantId, event.text);
          } else if (event.event === "query.completed") {
            const queryLogId =
              typeof event.query_log_id === "string" ? event.query_log_id : undefined;
            updateAssistant(assistantId, {
              complete: true,
              stage: undefined,
              queryLogId,
              provider: typeof event.provider === "string" ? event.provider : provider,
              model: typeof event.model === "string" ? event.model : undefined,
              latencyMs:
                typeof event.latency_ms === "number" ? event.latency_ms : undefined,
              cacheHit:
                typeof event.cache_hit === "boolean" ? event.cache_hit : undefined,
            });
            if (queryLogId) void loadTrace(assistantId, queryLogId);
          } else if (event.event === "query.failed") {
            updateAssistant(assistantId, {
              complete: true,
              stage: undefined,
              error:
                typeof event.error === "string" ? event.error : "The query failed.",
            });
          }
        },
      });
    } catch (error) {
      if (controller.signal.aborted) {
        updateAssistant(assistantId, {
          complete: true,
          stage: undefined,
          error:
            "Streaming was stopped in this browser. The backend may still finish and save the query.",
        });
      } else {
        updateAssistant(assistantId, {
          complete: true,
          stage: undefined,
          error: error instanceof Error ? error.message : "The query stream failed.",
        });
      }
    } finally {
      setStreaming(false);
      controllerRef.current = null;
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-5rem)] flex-col gap-6">
      <PageHeader
        eyebrow={project?.name ?? "Project"}
        title="Ask RAGForge"
        description="Answers stream from the selected project's indexed knowledge, with durable query and retrieval traces."
      />

      <Card className="flex min-h-[650px] flex-1 flex-col overflow-hidden">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm">
              <span className="size-2 rounded-full bg-[var(--success)]" />
              <span className="font-medium">{indexedDocuments.length} indexed</span>
              <span className="text-[var(--ink-muted)]">
                {indexedDocuments.length === 1 ? "document" : "documents"}
              </span>
            </div>
            <button
              className="flex items-center gap-1.5 text-xs font-semibold text-[var(--ink-muted)] hover:text-[var(--ink)]"
              onClick={() => setAdvanced((value) => !value)}
            >
              Query settings
              <ChevronDown
                className={cn("size-4 transition", advanced && "rotate-180")}
              />
            </button>
          </div>
          {advanced ? (
            <div className="mt-4 grid gap-3 rounded-xl bg-[var(--surface-muted)] p-4 sm:grid-cols-2">
              <label>
                <span className="mb-1.5 block text-xs font-semibold">Provider</span>
                <select
                  className="h-10 w-full rounded-lg border border-[var(--border)] bg-white px-3 text-sm"
                  value={provider}
                  onChange={(event) =>
                    setProvider(event.target.value as "gemini" | "groq")
                  }
                >
                  <option value="gemini">Gemini</option>
                  <option value="groq">Groq</option>
                </select>
              </label>
              <label>
                <span className="mb-1.5 block text-xs font-semibold">
                  Search scope
                </span>
                <select
                  className="h-10 w-full rounded-lg border border-[var(--border)] bg-white px-3 text-sm"
                  value={documentId}
                  onChange={(event) => setDocumentId(event.target.value)}
                >
                  <option value="">All indexed documents</option>
                  {indexedDocuments.map((document) => (
                    <option key={document.document_id} value={document.document_id}>
                      {document.filename}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}
        </div>

        <div className="flex-1 space-y-7 overflow-y-auto px-4 py-6 sm:px-7">
          {!messages.length ? (
            <div className="flex min-h-[420px] flex-col items-center justify-center text-center">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent)]">
                <Sparkles className="size-7" />
              </div>
              <h2 className="mt-5 text-xl font-semibold">
                Ask your knowledge base
              </h2>
              <p className="mt-2 max-w-lg text-sm leading-6 text-[var(--ink-muted)]">
                RAGForge searches indexed evidence, ranks the strongest sections,
                and streams a grounded answer with inspectable sources.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                  "Summarize the main policy",
                  "What are the key requirements?",
                  "Compare the documented options",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    className="rounded-full border border-[var(--border)] bg-white px-3.5 py-2 text-xs font-medium text-[var(--ink-muted)] hover:border-indigo-200 hover:text-[var(--accent)]"
                    onClick={() => setQuestion(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex gap-3",
                  message.role === "user" && "justify-end",
                )}
              >
                {message.role === "assistant" ? (
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-white">
                    <Bot className="size-4.5" />
                  </div>
                ) : null}
                <div
                  className={cn(
                    "max-w-3xl",
                    message.role === "user" &&
                      "rounded-2xl rounded-br-md bg-[var(--surface-dark)] px-4 py-3 text-sm leading-6 text-white",
                    message.role === "assistant" && "min-w-0 flex-1",
                  )}
                >
                  {message.role === "assistant" && message.stage ? (
                    <div className="mb-3 flex items-center gap-2 text-sm text-[var(--ink-muted)]">
                      <LoaderCircle className="size-4 animate-spin text-[var(--accent)]" />
                      {STAGE_LABELS[message.stage] ?? "Working"}
                    </div>
                  ) : null}
                  {message.role === "assistant" && message.text ? (
                    <div className="markdown-answer">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.text}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    message.text
                  )}
                  {message.error ? (
                    <div className="mt-3 rounded-xl bg-[var(--danger-soft)] p-3 text-sm leading-6 text-[var(--danger)]">
                      {message.error}
                    </div>
                  ) : null}
                  {message.role === "assistant" && message.complete && !message.error ? (
                    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-3">
                      {message.provider ? (
                        <Badge tone="info">{message.provider}</Badge>
                      ) : null}
                      {message.model ? <Badge>{message.model}</Badge> : null}
                      {message.cacheHit ? <Badge tone="success">cache hit</Badge> : null}
                      {message.latencyMs !== undefined ? (
                        <span className="text-xs text-[var(--ink-faint)]">
                          {formatLatency(message.latencyMs)}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {message.sources?.length ? (
                    <details className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)]">
                      <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold">
                        <span className="inline-flex items-center gap-2">
                          <FileSearch className="size-4 text-[var(--accent)]" />
                          Sources ({message.sources.length})
                        </span>
                      </summary>
                      <div className="space-y-3 border-t border-[var(--border)] p-3">
                        {message.sources.map((source) => (
                          <div key={source.retrieval_log_id} className="rounded-lg bg-white p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-semibold">
                                #{source.rank} · {source.document_name || "Indexed document"}
                              </p>
                              <span className="text-[10px] text-[var(--ink-faint)]">
                                {source.retrieval_strategy}
                              </span>
                            </div>
                            <p className="mt-2 line-clamp-4 text-xs leading-5 text-[var(--ink-muted)]">
                              {source.text}
                            </p>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : null}
                </div>
                {message.role === "user" ? (
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-slate-200 text-slate-600">
                    <UserRound className="size-4.5" />
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>

        <div className="border-t border-[var(--border)] bg-white p-4 sm:p-5">
          <div className="flex items-end gap-3 rounded-2xl border border-[var(--border-strong)] bg-white p-2 shadow-lg shadow-slate-900/5 focus-within:border-indigo-300 focus-within:ring-4 focus-within:ring-[var(--accent-soft)]">
            <textarea
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm leading-6 outline-none placeholder:text-[var(--ink-faint)]"
              placeholder={
                indexedDocuments.length
                  ? "Ask something about your documents..."
                  : "Index a document before asking a question"
              }
              value={question}
              disabled={!indexedDocuments.length}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendQuestion();
                }
              }}
            />
            {streaming ? (
              <Button
                size="icon"
                variant="secondary"
                aria-label="Stop streaming"
                onClick={() => controllerRef.current?.abort()}
              >
                <CircleStop className="size-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                aria-label="Send question"
                disabled={!question.trim() || !indexedDocuments.length}
                onClick={() => void sendQuestion()}
              >
                <Send className="size-4" />
              </Button>
            )}
          </div>
          <p className="mt-2 text-center text-[10px] text-[var(--ink-faint)]">
            Answers are grounded in retrieved project documents. Verify critical information.
          </p>
        </div>
      </Card>
    </div>
  );
}
