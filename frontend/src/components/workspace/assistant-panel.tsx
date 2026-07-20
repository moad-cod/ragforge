"use client";

import {useQuery} from "@tanstack/react-query";
import {
  Clock3,
  ChevronDown,
  CircleStop,
  Copy,
  FilePlus2,
  History,
  LoaderCircle,
  MessageSquareText,
  MoreHorizontal,
  PanelTop,
  RefreshCw,
  Search,
  Send,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import {useRef, useState} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {toast} from "sonner";
import {apiFetch} from "@/lib/api";
import {consumeSSE} from "@/lib/sse";
import type {QueryHistoryItem, QueryTrace, RetrievalTrace, StreamEvent} from "@/lib/types";
import {cn} from "@/lib/utils";
import type {WorkspaceDocument} from "@/components/workspace/workspace-data";

type Message = {id: string; role: "user" | "assistant"; text: string; complete: boolean; stage?: string; sources?: RetrievalTrace[]; timestamp: string; error?: string};

const stages = [
  "Understanding question",
  "Searching dense and sparse indexes",
  "Reranking sources",
  "Generating answer",
  "Saving query trace",
];

const suggestions = ["Summarize the key findings", "Compare the uploaded documents", "Explain the main methodology", "Identify important risks or limitations"];

function CitationChip({source, onClick}: {source: RetrievalTrace; onClick: () => void}) {
  const [preview, setPreview] = useState(false);
  return <span className="relative inline-block" onMouseEnter={() => setPreview(true)} onMouseLeave={() => setPreview(false)}>
    <button onClick={onClick} className="inline-flex h-6 items-center gap-1 rounded-md border border-emerald-400/20 bg-emerald-400/[0.07] px-2 text-[9px] font-medium text-emerald-200 hover:border-emerald-400/40 hover:bg-emerald-400/10">
      <FilePlus2 className="size-2.5" />{source.document_name?.replace(/\.(pdf|docx|xlsx)$/i, "")} · p.{source.page_start}
    </button>
    {preview ? <span className="absolute bottom-[calc(100%+7px)] left-0 z-50 block w-64 rounded-lg border border-white/10 bg-[#13251e] p-3 text-left shadow-2xl">
      <span className="flex items-center justify-between"><b className="max-w-44 truncate text-[10px] text-[#e5ece8]">{source.document_name}</b><span className="font-mono text-[9px] text-emerald-300">{Math.round((source.rerank_score ?? source.qdrant_score ?? 0) * 100)}%</span></span>
      <span className="mt-1 block text-[8px] text-[#64736d]">Page {source.page_start} · Chunk {source.chunk_index} · {source.retrieval_strategy}</span>
      <span className="mt-2 block text-[9px] leading-4 text-[#a9b7b0]">{source.text}</span>
    </span> : null}
  </span>;
}

function AssistantMessage({message, onCitation, onTrace}: {message: Message; onCitation: (source: RetrievalTrace) => void; onTrace: () => void}) {
  return <div className="group flex gap-3">
    <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg border border-emerald-400/20 bg-emerald-400/10 text-emerald-300"><Sparkles className="size-3.5" /></div>
    <div className="min-w-0 max-w-[760px] flex-1">
      <div className="mb-2 flex items-center gap-2"><span className="text-[10px] font-semibold text-[#dce6e1]">RAGForge Assistant</span><span className="text-[9px] text-[#53625b]">{message.timestamp}</span></div>
      {message.stage ? <div className="mb-3 rounded-lg border border-white/[0.07] bg-white/[0.02] p-2.5"><div className="flex items-center gap-2 text-[10px] text-[#a9b7b0]"><LoaderCircle className="size-3.5 animate-spin text-emerald-400" />{message.stage}</div><div className="mt-2 flex gap-1">{stages.map((stage) => <span key={stage} className={cn("h-0.5 flex-1 rounded-full", stages.indexOf(stage) <= stages.indexOf(message.stage ?? "") ? "bg-emerald-400" : "bg-white/10")} />)}</div></div> : null}
      {message.text ? <div className="markdown-answer text-[12px]"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown></div> : null}
      {message.error ? <div className="rounded-lg border border-red-400/20 bg-red-400/[0.07] p-3 text-[10px] leading-5 text-red-200">{message.error}</div> : null}
      {message.sources?.length ? <div className="mt-4 flex flex-wrap gap-1.5">{message.sources.filter((source) => source.used_in_answer).map((source) => <CitationChip key={source.retrieval_log_id} source={source} onClick={() => onCitation(source)} />)}<button onClick={onTrace} className="h-6 rounded-md px-2 text-[9px] text-[#71847b] hover:bg-white/5 hover:text-[#cbd5d0]">View retrieval trace →</button></div> : null}
      {message.complete ? <div className="mt-4 flex items-center gap-0.5 border-t border-white/[0.07] pt-2 text-[#64736d]"><button title="Copy answer" onClick={() => {navigator.clipboard?.writeText(message.text); toast.success("Answer copied");}} className="flex size-6 items-center justify-center rounded hover:bg-white/5 hover:text-white"><Copy className="size-3" /></button><button title="Regenerate" className="flex size-6 items-center justify-center rounded hover:bg-white/5 hover:text-white"><RefreshCw className="size-3" /></button><button title="Helpful" className="flex size-6 items-center justify-center rounded hover:bg-white/5 hover:text-white"><ThumbsUp className="size-3" /></button><button title="Not helpful" className="flex size-6 items-center justify-center rounded hover:bg-white/5 hover:text-white"><ThumbsDown className="size-3" /></button><button onClick={onTrace} className="ml-1 flex items-center gap-1 rounded px-1.5 py-1 text-[8px] hover:bg-white/5 hover:text-white"><PanelTop className="size-2.5" />Retrieval details</button></div> : null}
    </div>
  </div>;
}

function HistoryDrawer({projectId, onClose, onRestore}: {projectId: string; onClose: () => void; onRestore: (trace: QueryTrace) => void}) {
  const {data: items = [], isLoading, isError} = useQuery({
    queryKey: ["query-history", projectId],
    queryFn: () => apiFetch<QueryHistoryItem[]>(`/rag/projects/${projectId}/history?limit=100`),
  });
  async function restore(id: string) {
    try { onRestore(await apiFetch<QueryTrace>(`/rag/queries/${id}`)); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Unable to restore this query"); }
  }
  return <div className="absolute inset-y-0 right-0 z-50 w-full max-w-sm border-l border-white/10 bg-[#0e1c17] shadow-2xl">
    <div className="flex h-12 items-center justify-between border-b border-white/10 px-4"><div><h3 className="text-[12px] font-semibold">Query history</h3><p className="text-[8px] text-[#64736d]">Recent conversations in this project</p></div><button onClick={onClose} className="flex size-7 items-center justify-center rounded hover:bg-white/5"><X className="size-3.5" /></button></div>
    <div className="p-2"><label className="flex h-8 items-center gap-2 rounded-lg border border-white/[0.08] px-2"><Search className="size-3 text-[#64736d]" /><input className="min-w-0 flex-1 bg-transparent text-[10px] outline-none" placeholder="Search query history" /></label></div>
    <div className="overflow-y-auto px-2 pb-4">{isLoading ? <p className="p-4 text-center text-[9px] text-[#64736d]">Loading query history…</p> : isError ? <p className="p-4 text-center text-[9px] text-red-300">Query history could not be loaded.</p> : items.length ? items.map((item) => <button onClick={() => void restore(item.query_log_id)} key={item.query_log_id} className="mb-1 w-full rounded-lg border border-transparent p-3 text-left hover:border-white/[0.08] hover:bg-white/[0.025]"><div className="flex items-start justify-between gap-2"><h4 className="text-[10px] font-medium leading-4 text-[#dce6e1]">{item.question}</h4><MoreHorizontal className="size-3 shrink-0 text-[#64736d]" /></div><p className="mt-1 line-clamp-2 text-[9px] leading-4 text-[#71847b]">{item.answer ?? "This query did not produce an answer."}</p><div className="mt-2 flex flex-wrap items-center gap-1.5 text-[8px] text-[#53625b]"><span>{new Date(item.created_at).toLocaleString()}</span>{item.model ? <><span>·</span><span>{item.model}</span></> : null}{item.latency_ms !== null ? <><span>·</span><span>{(item.latency_ms / 1000).toFixed(1)}s</span></> : null}{item.cache_hit ? <span className="rounded bg-emerald-400/10 px-1 text-emerald-300">Cache hit</span> : null}</div></button>) : <div className="p-8 text-center"><Clock3 className="mx-auto size-5 text-[#53625b]" /><p className="mt-2 text-[10px] text-[#93a39c]">No query history yet</p><p className="mt-1 text-[8px] text-[#53625b]">Completed queries will appear here.</p></div>}</div>
  </div>;
}

export function AssistantPanel({projectId, projectName, documents, selectedIds, onRemoveSelected, onCitation, onOpenTrace}: {
  projectId: string;
  projectName: string;
  documents: WorkspaceDocument[];
  selectedIds: string[];
  onRemoveSelected: (id: string) => void;
  onCitation: (source: RetrievalTrace) => void;
  onOpenTrace: () => void;
}) {
  const [mode, setMode] = useState<"Chat" | "Search">("Chat");
  const [question, setQuestion] = useState("");
  const [settings, setSettings] = useState(false);
  const [history, setHistory] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const controllerRef = useRef<AbortController | null>(null);
  const selected = documents.filter((doc) => selectedIds.includes(doc.document_id));
  const indexedDocuments = documents.filter((doc) => doc.status === "indexed");

  function update(id: string, patch: Partial<Message>) { setMessages((current) => current.map((message) => message.id === id ? {...message, ...patch} : message)); }

  async function loadTrace(assistantId: string, queryLogId: string) {
    try {
      const trace = await apiFetch<QueryTrace>(`/rag/queries/${queryLogId}`);
      update(assistantId, {sources: trace.retrievals});
    } catch {
      // The answer remains visible if trace loading fails.
    }
  }

  async function send() {
    const value = question.trim();
    if (!value || streaming) return;
    if (!indexedDocuments.length) {
      toast.error("Index at least one document before asking a question.");
      return;
    }
    const userId = crypto.randomUUID(); const assistantId = crypto.randomUUID();
    setMessages((current) => [...current, {id: userId, role: "user", text: value, complete: true, timestamp: "Now"}, {id: assistantId, role: "assistant", text: "", complete: false, timestamp: "Now", stage: stages[0]}]);
    setQuestion(""); setStreaming(true);
    const controller = new AbortController(); controllerRef.current = controller;
    try {
      const response = await fetch("/api/backend/rag/query/stream", {method: "POST", headers: {"Content-Type": "application/json", Accept: "text/event-stream"}, body: JSON.stringify({question: value, project_id: projectId, provider: "gemini", document_ids: selectedIds, include_context: true}), signal: controller.signal});
      if (!response.ok) throw new Error("Query service unavailable");
      await consumeSSE(response, {onEvent: (event: StreamEvent) => {
        const stageMap: Record<string, string> = {"query.received": stages[0], "query.retrieving": stages[1], "query.reranking": stages[2], "query.generating": stages[3]};
        if (stageMap[event.event]) update(assistantId, {stage: stageMap[event.event]});
        if (event.event === "query.token" && typeof event.text === "string") setMessages((current) => current.map((message) => message.id === assistantId ? {...message, text: message.text + event.text} : message));
        if (event.event === "query.completed") {
          update(assistantId, {complete: true, stage: undefined});
          if (typeof event.query_log_id === "string") void loadTrace(assistantId, event.query_log_id);
        }
        if (event.event === "query.failed") update(assistantId, {complete: true, stage: undefined, error: typeof event.error === "string" ? event.error : "The query failed."});
      }});
    } catch (error) {
      if (!controller.signal.aborted) update(assistantId, {complete: true, stage: undefined, error: error instanceof Error ? error.message : "The query service is unavailable."});
      else update(assistantId, {complete: true, stage: undefined, error: "Generation stopped."});
    } finally { setStreaming(false); controllerRef.current = null; }
  }

  return <section className="relative flex h-full min-w-0 flex-col bg-[#07110d]">
    <div className="flex h-[49px] shrink-0 items-center justify-between border-b border-white/[0.08] px-3 lg:px-4">
      <div><div className="flex items-center gap-2"><h2 className="text-[13px] font-semibold">RAGForge Assistant</h2><span className="hidden text-[9px] text-[#64736d] sm:inline">{projectName}</span></div><p className="mt-0.5 text-[8px] text-[#64736d]">Grounded in {selected.length || documents.filter((d) => d.status === "indexed").length} selected documents</p></div>
      <div className="flex items-center gap-1">
        <div className="mr-1 hidden rounded-lg bg-white/[0.035] p-0.5 sm:flex"><button onClick={() => setMode("Chat")} className={cn("flex h-6 items-center gap-1 rounded-md px-2 text-[8px]", mode === "Chat" ? "bg-[#173027] text-emerald-200" : "text-[#64736d]")}><MessageSquareText className="size-2.5" />Chat</button><button onClick={() => setMode("Search")} className={cn("flex h-6 items-center gap-1 rounded-md px-2 text-[8px]", mode === "Search" ? "bg-[#173027] text-emerald-200" : "text-[#64736d]")}><Search className="size-2.5" />Search</button></div>
        <button title="Query history" onClick={() => setHistory(true)} className="flex size-7 items-center justify-center rounded-lg text-[#64736d] hover:bg-white/5 hover:text-white"><History className="size-3.5" /></button>
        <button onClick={() => setMessages([])} className="flex h-7 items-center gap-1 rounded-lg border border-white/[0.08] px-2 text-[8px] text-[#a9b7b0] hover:bg-white/5"><RefreshCw className="size-2.5" />New chat</button>
      </div>
    </div>

    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
      {!messages.length ? <div className="flex h-full min-h-[360px] flex-col items-center justify-center text-center"><div className="flex size-10 items-center justify-center rounded-xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-300"><Sparkles className="size-5" /></div><h2 className="mt-4 text-[17px] font-semibold">Ask your knowledge base</h2><p className="mt-1.5 max-w-md text-[11px] leading-5 text-[#71847b]">Answers are generated from indexed project documents, with every claim connected to its supporting source.</p>{!indexedDocuments.length ? <div className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-[9px] text-amber-200">This project has no indexed documents yet.</div> : <div className="mt-5 grid w-full max-w-lg grid-cols-1 gap-1.5 sm:grid-cols-2">{suggestions.map((prompt) => <button key={prompt} onClick={() => setQuestion(prompt)} className="rounded-lg border border-white/[0.08] bg-white/[0.018] px-3 py-2.5 text-left text-[10px] text-[#a9b7b0] hover:border-emerald-400/20 hover:bg-emerald-400/[0.03] hover:text-white">{prompt}<span className="float-right text-[#53625b]">↗</span></button>)}</div>}</div> : <div className="mx-auto max-w-[810px] space-y-7">{messages.map((message) => message.role === "user" ? <div key={message.id} className="group flex justify-end"><div className="max-w-[78%]"><div className="rounded-xl rounded-br-sm border border-white/[0.08] bg-[#11221b] px-3.5 py-2.5 text-[11px] leading-5 text-[#e5ece8]">{message.text}</div><div className="mt-1 flex justify-end gap-1 text-[8px] text-[#53625b]"><span>{message.timestamp}</span><button title="Copy question" className="opacity-0 group-hover:opacity-100"><Copy className="size-2.5" /></button></div></div></div> : <AssistantMessage key={message.id} message={message} onCitation={onCitation} onTrace={onOpenTrace} />)}</div>}
    </div>

    <div className="shrink-0 bg-gradient-to-t from-[#07110d] via-[#07110d] to-transparent px-3 pb-3 pt-2 sm:px-5">
      <div className="mx-auto max-w-[840px]">
        {selected.length ? <div className="mb-1.5 flex gap-1.5 overflow-x-auto">{selected.map((doc) => <span key={doc.document_id} className="flex h-5 shrink-0 items-center gap-1 rounded bg-white/[0.045] px-1.5 text-[8px] text-[#93a39c]"><FilePlus2 className="size-2.5 text-emerald-300" /><span className="max-w-32 truncate">{doc.filename}</span><button onClick={() => onRemoveSelected(doc.document_id)}><X className="size-2.5" /></button></span>)}</div> : null}
        <div className="relative rounded-xl border border-white/[0.13] bg-[#0e1c17] shadow-[0_12px_35px_rgba(0,0,0,.24)] focus-within:border-emerald-400/35">
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => {if (event.key === "Enter" && !event.shiftKey) {event.preventDefault(); void send();} if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {event.preventDefault(); void send();}}} placeholder="Ask a question about your knowledge base…" className="block min-h-[56px] max-h-32 w-full resize-none bg-transparent px-3.5 py-3 text-[11px] leading-5 outline-none placeholder:text-[#53625b]" />
          <div className="flex items-center justify-between px-2 pb-2"><div className="flex items-center gap-0.5"><button title="Select documents" className="flex size-6 items-center justify-center rounded text-[#64736d] hover:bg-white/5 hover:text-white"><FilePlus2 className="size-3" /></button><button onClick={() => setSettings((value) => !value)} title="Retrieval settings" className={cn("flex size-6 items-center justify-center rounded hover:bg-white/5 hover:text-white", settings ? "bg-emerald-400/10 text-emerald-300" : "text-[#64736d]")}><SlidersHorizontal className="size-3" /></button><button className="flex h-6 items-center gap-1 rounded px-1.5 text-[8px] text-[#71847b] hover:bg-white/5"><span className="flex size-3 items-center justify-center rounded bg-[#4285f4] text-[7px] font-bold text-white">G</span>Gemini 2.5 Flash<ChevronDown className="size-2.5" /></button></div><div className="flex items-center gap-2"><span className="hidden text-[8px] text-[#53625b] sm:block">Enter to send · Shift + Enter for new line</span>{streaming ? <button onClick={() => controllerRef.current?.abort()} aria-label="Stop generation" className="flex size-7 items-center justify-center rounded-lg bg-white/10 text-white"><CircleStop className="size-3.5" /></button> : <button onClick={() => void send()} disabled={!question.trim()} aria-label="Send question" className="flex size-7 items-center justify-center rounded-lg bg-emerald-400 text-[#052116] hover:bg-emerald-300 disabled:bg-white/[0.07] disabled:text-[#53625b]"><Send className="size-3.5" /></button>}</div></div>
          {settings ? <div className="absolute bottom-[calc(100%+7px)] left-0 w-72 rounded-lg border border-white/10 bg-[#13251e] p-3 shadow-2xl"><div className="mb-2 flex items-center justify-between"><h3 className="text-[10px] font-semibold">Retrieval settings</h3><Settings2 className="size-3 text-[#64736d]" /></div>{[["Search all project documents", false], ["Use parent context", true], ["Enable reranking", true], ["Include retrieved context", true]].map(([label, checked]) => <label key={String(label)} className="flex items-center justify-between py-1.5 text-[9px] text-[#a9b7b0]"><span>{label}</span><span className={cn("flex h-3.5 w-6 items-center rounded-full p-0.5", checked ? "justify-end bg-emerald-400" : "bg-white/10")}><span className="size-2.5 rounded-full bg-white" /></span></label>)}<label className="mt-2 block text-[8px] text-[#64736d]">Number of results <input type="range" min="3" max="12" defaultValue="8" className="mt-1 w-full accent-emerald-400" /></label></div> : null}
        </div>
        <p className="mt-1.5 text-center text-[8px] text-[#40524a]">RAGForge can make mistakes. Verify important information against cited sources.</p>
      </div>
    </div>
    {history ? <HistoryDrawer projectId={projectId} onClose={() => setHistory(false)} onRestore={(trace) => {setMessages([{id: `${trace.query_log_id}-user`, role: "user", text: trace.question, complete: true, timestamp: new Date(trace.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}, {id: `${trace.query_log_id}-assistant`, role: "assistant", text: trace.answer ?? "", error: trace.answer ? undefined : "This query did not produce an answer.", complete: true, timestamp: new Date(trace.created_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}), sources: trace.retrievals}]); setHistory(false);}} /> : null}
  </section>;
}
