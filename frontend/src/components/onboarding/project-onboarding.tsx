"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  Cloud,
  Database,
  FileText,
  Globe2,
  HardDriveUpload,
  LoaderCircle,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import {useRouter} from "next/navigation";
import {useEffect, useMemo, useRef, useState} from "react";
import {toast} from "sonner";
import {apiFetch} from "@/lib/api";
import type {Chunker, Document, IngestionRun, Project} from "@/lib/types";
import {cn} from "@/lib/utils";
import {useIngestionStream} from "@/hooks/use-ingestion-stream";

type OnboardingStep = "knowledge" | "configure" | "processing" | "success";
type SourceMode = "file" | "url" | "gdrive";
type PendingSource =
  | {id: string; kind: "file"; file: File; name: string; detail: string}
  | {id: string; kind: "url"; url: string; name: string; detail: string}
  | {id: string; kind: "gdrive"; fileId: string; accessToken: string; name: string; detail: string};

const progressSteps = ["Project details", "Add knowledge", "Configure ingestion", "Process documents"];

const pipelineStages = [
  {name: "Upload complete", description: "Your file was validated and securely received."},
  {name: "Bronze storage", description: "The original source is safely stored and versioned."},
  {name: "Parsing and chunking", description: "Content is extracted and split into retrieval-ready sections."},
  {name: "Embedding generation", description: "Semantic representations are generated for every chunk."},
  {name: "Qdrant indexing", description: "Chunks and vectors are published to the search index."},
  {name: "Knowledge base ready", description: "Your document is ready for grounded questions."},
];

const statusRank: Record<string, number> = {
  landed: 1,
  queued: 1,
  running: 2,
  silver_completed: 3,
  gold_completed: 4,
  indexed: 5,
};

function OnboardingProgress({step}: {step: OnboardingStep}) {
  const active = step === "knowledge" ? 1 : step === "configure" ? 2 : 3;
  return <div className="mx-auto flex w-full max-w-3xl items-start">
    {progressSteps.map((label, index) => <div key={label} className="flex flex-1 items-start last:flex-none">
      <div className="flex w-24 flex-col items-center text-center sm:w-36"><span className={cn("flex size-7 items-center justify-center rounded-full border text-[10px] font-semibold", index < active ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--ink-inverse)]" : index === active ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]" : "border-white/10 bg-white/[0.025] text-[#53625b]")}>{index < active ? <Check className="size-3.5" /> : index + 1}</span><span className={cn("mt-2 hidden text-[9px] sm:block", index <= active ? "text-[#c4d1cb]" : "text-[#53625b]")}>{label}</span></div>
      {index < progressSteps.length - 1 ? <span className={cn("mt-3.5 h-px min-w-4 flex-1", index < active ? "bg-[var(--accent)]/60" : "bg-white/10")} /> : null}
    </div>)}
  </div>;
}

function ProcessingRun({initialRun, filename, onStatus}: {initialRun: IngestionRun; filename: string; onStatus: (run: IngestionRun) => void}) {
  const {run, connected} = useIngestionStream(initialRun);
  const lastReported = useRef("");
  const [now, setNow] = useState(() => Date.now());
  const failed = run.status === "failed" || run.status === "cancelled";
  const rank = statusRank[run.status] ?? 0;

  useEffect(() => {
    if (lastReported.current === run.status) return;
    lastReported.current = run.status;
    onStatus(run);
  }, [onStatus, run]);

  useEffect(() => {
    if (run.finished_at) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [run.finished_at]);

  const start = new Date(run.started_at ?? run.created_at).getTime();
  const end = run.finished_at ? new Date(run.finished_at).getTime() : now;
  const elapsed = Math.max(0, Math.floor((end - start) / 1000));

  return <section className="rounded-xl border border-white/[0.09] bg-[var(--surface)]">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] px-4 py-3">
      <div className="flex min-w-0 items-center gap-3"><span className="flex size-8 items-center justify-center rounded-lg bg-red-400/10 text-red-300"><FileText className="size-4" /></span><div className="min-w-0"><h3 className="truncate text-[12px] font-medium">{filename}</h3><p className="mt-0.5 font-mono text-[8px] text-[#53625b]">{run.ingestion_run_id}</p></div></div>
      {!failed && run.status !== "indexed" ? <span className={cn("flex items-center gap-1.5 rounded-full border px-2 py-1 text-[8px]", connected ? "border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent)]" : "border-amber-400/20 bg-amber-400/[0.07] text-amber-300")}><span className={cn("size-1.5 rounded-full", connected ? "bg-[var(--accent)]" : "bg-amber-400")} />{connected ? "Live pipeline updates" : "Reconnecting to pipeline…"}</span> : null}
    </div>
    <div className="p-4 sm:p-5">
      {failed ? <div className="rounded-lg border border-red-400/20 bg-red-400/[0.055] p-4"><div className="flex gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0 text-red-300" /><div><h4 className="text-[11px] font-semibold text-red-200">We could not complete document indexing.</h4><p className="mt-1 text-[9px] leading-4 text-red-200/70">Your uploaded file is safe and you can retry the failed stage.</p><p className="mt-3 rounded-md bg-black/15 p-2 font-mono text-[8px] leading-4 text-red-200/80">{run.error_message || "The ingestion pipeline stopped unexpectedly."}</p></div></div></div> : <div className="space-y-0">{pipelineStages.map((stage, index) => {
        const stageRank = index;
        const complete = run.status === "indexed" || rank > stageRank;
        const active = run.status !== "indexed" && rank === stageRank;
        return <div key={stage.name} className="flex gap-3"><div className="flex flex-col items-center"><span className={cn("flex size-6 shrink-0 items-center justify-center rounded-full border", complete ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--ink-inverse)]" : active ? "border-blue-400 bg-blue-400/10 text-blue-300" : "border-white/10 bg-white/[0.02] text-[#40524a]")}>{complete ? <Check className="size-3" /> : active ? <LoaderCircle className="size-3 animate-spin" /> : <Circle className="size-2.5" />}</span>{index < pipelineStages.length - 1 ? <span className={cn("h-10 w-px", complete ? "bg-[var(--accent-muted)]" : "bg-white/[0.08]")} /> : null}</div><div className="min-w-0 flex-1 pb-4"><div className="flex items-center justify-between gap-2"><h4 className={cn("text-[10px] font-medium", complete || active ? "text-[#dce6e1]" : "text-[#64736d]")}>{stage.name}</h4><span className="text-[8px] capitalize text-[#53625b]">{complete ? "Completed" : active ? "Running" : "Waiting"}</span></div><p className="mt-0.5 text-[8px] leading-4 text-[#53625b]">{stage.description}</p></div></div>;
      })}</div>}
      <div className="mt-1 flex items-center justify-between border-t border-white/[0.07] pt-3 text-[8px] text-[#53625b]"><span>Elapsed {elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`}</span><span>{run.status === "indexed" ? "100%" : `${Math.min(90, Math.max(10, rank * 18))}%`}</span></div>
    </div>
  </section>;
}

export function ProjectOnboarding({projectId}: {projectId: string}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<SourceMode>("file");
  const [sources, setSources] = useState<PendingSource[]>([]);
  const [step, setStep] = useState<OnboardingStep>("knowledge");
  const [chunkerId, setChunkerId] = useState(() => typeof window === "undefined" ? "paragraph" : localStorage.getItem(`ragforge:project:${projectId}:chunker`) ?? "paragraph");
  const [advanced, setAdvanced] = useState(false);
  const [url, setUrl] = useState("");
  const [driveId, setDriveId] = useState("");
  const [driveToken, setDriveToken] = useState("");
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [successCount, setSuccessCount] = useState(0);
  const [successChunks, setSuccessChunks] = useState(0);

  const {data: project} = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`)});
  const {data: documents = []} = useQuery({queryKey: ["documents", projectId], queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`)});
  const {data: persistedRuns = []} = useQuery({queryKey: ["ingestion-runs", projectId], queryFn: () => apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${projectId}&limit=30`), refetchInterval: 10_000});
  const {data: chunkers = []} = useQuery({queryKey: ["chunkers"], queryFn: () => apiFetch<Chunker[]>("/chunkers")});

  const sourceNameByDocument = useMemo(() => new Map(documents.map((document) => [document.document_id, document.filename ?? "Document"])), [documents]);
  const validSources = sources.length > 0;
  const indexedDocuments = documents.filter((document) => document.status === "indexed");
  const effectiveRuns = runs.length ? runs : persistedRuns.filter((run) => run.status !== "indexed");
  const effectiveStep: OnboardingStep = indexedDocuments.length ? "success" : effectiveRuns.length && step === "knowledge" && !sources.length ? "processing" : step;

  function addFiles(files: FileList | File[]) {
    const accepted = Array.from(files).filter((file) => file.size <= 25 * 1024 * 1024);
    if (accepted.length !== Array.from(files).length) toast.error("Files larger than 25 MB were not added.");
    setSources((current) => [...current, ...accepted.map((file) => ({id: crypto.randomUUID(), kind: "file" as const, file, name: file.name, detail: file.size > 1_000_000 ? `${(file.size / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(file.size / 1000))} KB`}))]);
  }

  function addRemoteSource() {
    if (mode === "url") {
      try { const parsed = new URL(url); setSources((current) => [...current, {id: crypto.randomUUID(), kind: "url", url: parsed.toString(), name: parsed.hostname, detail: parsed.toString()}]); setUrl(""); }
      catch { toast.error("Enter a valid public URL."); }
    } else if (mode === "gdrive") {
      if (!driveId.trim() || !driveToken.trim()) { toast.error("Google Drive file ID and access token are required."); return; }
      setSources((current) => [...current, {id: crypto.randomUUID(), kind: "gdrive", fileId: driveId.trim(), accessToken: driveToken.trim(), name: `Google Drive file ${driveId.trim()}`, detail: "Google Drive"}]); setDriveId(""); setDriveToken("");
    }
  }

  const createKnowledgeBase = useMutation({
    mutationFn: async () => {
      const createdRuns: IngestionRun[] = [];
      let immediateIndexed = 0;
      let chunks = 0;
      for (const source of sources) {
        if (source.kind === "file") {
          const form = new FormData(); form.set("project_id", projectId); form.set("chunker", chunkerId); form.set("file", source.file);
          const landing = await apiFetch<{ingestion_run_id: string}>("/ingest/file", {method: "POST", body: form});
          createdRuns.push(await apiFetch<IngestionRun>(`/ingest/runs/${landing.ingestion_run_id}`));
        } else if (source.kind === "url") {
          const result = await apiFetch<{chunks_indexed: number}>("/ingest/url", {method: "POST", body: JSON.stringify({project_id: projectId, chunker: chunkerId, url: source.url})});
          immediateIndexed += 1; chunks += result.chunks_indexed ?? 0;
        } else {
          const result = await apiFetch<{chunks_indexed: number}>("/ingest/gdrive", {method: "POST", body: JSON.stringify({project_id: projectId, chunker: chunkerId, file_id: source.fileId, access_token: source.accessToken})});
          immediateIndexed += 1; chunks += result.chunks_indexed ?? 0;
        }
      }
      return {createdRuns, immediateIndexed, chunks};
    },
    onMutate: () => setStep("processing"),
    onSuccess: async ({createdRuns, immediateIndexed, chunks}) => {
      setRuns(createdRuns); setSuccessCount(immediateIndexed); setSuccessChunks(chunks);
      await Promise.all([queryClient.invalidateQueries({queryKey: ["documents", projectId]}), queryClient.invalidateQueries({queryKey: ["ingestion-runs", projectId]})]);
      setStep(createdRuns.length ? "processing" : "success");
    },
    onError: (error) => {setStep("configure"); toast.error(error instanceof Error ? error.message : "Knowledge-base creation failed");},
  });

  const retry = useMutation({
    mutationFn: (runId: string) => apiFetch<IngestionRun>(`/ingest/runs/${runId}/retry`, {method: "POST"}),
    onSuccess: (retried) => setRuns((current) => current.map((run) => run.ingestion_run_id === retried.ingestion_run_id ? retried : run)),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to retry ingestion"),
  });

  function handleRunStatus(updated: IngestionRun) {
    setRuns((current) => current.some((run) => run.ingestion_run_id === updated.ingestion_run_id)
      ? current.map((run) => run.ingestion_run_id === updated.ingestion_run_id ? updated : run)
      : [updated, ...current]);
    void queryClient.invalidateQueries({queryKey: ["documents", projectId]});
    if (updated.status === "indexed") {
      setSuccessCount((current) => Math.max(1, current + 1));
      setStep("success");
    }
  }

  const failedRun = effectiveRuns.find((run) => run.status === "failed" || run.status === "cancelled");
  const pageStep = effectiveStep === "success" ? "processing" : effectiveStep;

  return <div className="h-full overflow-y-auto bg-[var(--background)]">
    <div className="mx-auto min-h-full max-w-5xl px-4 py-6 sm:px-7 sm:py-8">
      <div className="flex items-center justify-between"><button onClick={() => router.push("/projects")} className="flex items-center gap-1.5 text-[10px] text-[#71847b] hover:text-white"><ArrowLeft className="size-3" />Back to projects</button><span className="max-w-48 truncate text-[10px] text-[#64736d]">{project?.name ?? "Project"}</span></div>
      <div className="mt-7"><OnboardingProgress step={pageStep} /></div>

      {effectiveStep === "knowledge" ? <section className="mx-auto mt-10 max-w-3xl">
        <div className="text-center"><p className="text-[10px] font-semibold uppercase tracking-[.15em] text-[var(--accent)]">Step 2 of 4</p><h1 className="mt-2 text-2xl font-semibold">Add knowledge to your project</h1><p className="mx-auto mt-2 max-w-xl text-[12px] leading-5 text-[#71847b]">Upload at least one document to prepare your RAGForge knowledge base. You can add more sources later from the workspace.</p></div>
        <div className="mt-7 rounded-xl border border-white/[0.09] bg-[var(--surface)] p-3 sm:p-5">
          <div className="grid grid-cols-3 gap-1 rounded-lg bg-white/[0.025] p-1">{([{id:"file",label:"Upload files",icon:UploadCloud},{id:"url",label:"Add a URL",icon:Globe2},{id:"gdrive",label:"Google Drive",icon:Cloud}] as const).map(({id,label,icon:Icon}) => <button key={id} onClick={() => setMode(id)} className={cn("flex h-9 items-center justify-center gap-1.5 rounded-md text-[9px]", mode === id ? "bg-[var(--surface-active)] text-[var(--accent-hover)]" : "text-[#64736d] hover:text-[#a9b7b0]")}><Icon className="size-3" />{label}</button>)}</div>
          {mode === "file" ? <button onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => {event.preventDefault(); addFiles(event.dataTransfer.files);}} className="mt-3 flex min-h-48 w-full flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.16] bg-white/[0.015] px-5 text-center transition hover:border-[var(--border-hover)] hover:bg-[var(--accent-soft)]"><span className="flex size-11 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]"><HardDriveUpload className="size-5" /></span><strong className="mt-4 text-[12px] font-medium">Drop your files here or browse your computer</strong><span className="mt-1.5 text-[9px] text-[#64736d]">PDF, DOCX, PPTX, XLSX, CSV, TXT and HTML · Maximum 25 MB per file</span></button> : mode === "url" ? <div className="mt-3 rounded-xl border border-white/[0.09] p-5"><label className="text-[10px] font-medium">Public webpage URL</label><div className="mt-2 flex gap-2"><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/research" className="h-10 min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[0.025] px-3 text-[10px] outline-none focus:border-[var(--border-hover)]" /><button onClick={addRemoteSource} className="rounded-lg bg-[var(--accent)] px-4 text-[9px] font-semibold text-[var(--ink-inverse)]">Add URL</button></div></div> : <div className="mt-3 space-y-3 rounded-xl border border-white/[0.09] p-5"><label className="block text-[10px] font-medium">Google Drive file ID<input value={driveId} onChange={(event) => setDriveId(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-white/10 bg-white/[0.025] px-3 text-[10px] outline-none focus:border-[var(--border-hover)]" /></label><label className="block text-[10px] font-medium">Access token<input type="password" value={driveToken} onChange={(event) => setDriveToken(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-white/10 bg-white/[0.025] px-3 text-[10px] outline-none focus:border-[var(--border-hover)]" /></label><button onClick={addRemoteSource} className="h-9 rounded-lg bg-[var(--accent)] px-4 text-[9px] font-semibold text-[var(--ink-inverse)]">Add Google Drive file</button></div>}
          <input ref={inputRef} className="hidden" multiple type="file" accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.html,.htm" onChange={(event) => event.target.files && addFiles(event.target.files)} />
          {sources.length ? <div className="mt-4"><p className="mb-2 text-[9px] font-medium text-[#93a39c]">Ready to add ({sources.length})</p><div className="space-y-1.5">{sources.map((source) => <div key={source.id} className="flex items-center gap-3 rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2.5"><FileText className="size-4 text-[var(--accent)]" /><div className="min-w-0 flex-1"><p className="truncate text-[10px] font-medium">{source.name}</p><p className="truncate text-[8px] text-[#53625b]">{source.kind.toUpperCase()} · {source.detail}</p></div><span className="rounded-full bg-[var(--accent-soft)] px-2 py-1 text-[7px] text-[var(--accent)]">Valid</span><button onClick={() => setSources((current) => current.filter((item) => item.id !== source.id))} className="text-[#53625b] hover:text-white"><X className="size-3" /></button></div>)}</div></div> : null}
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><button onClick={() => router.push("/projects")} className="text-[9px] text-[#71847b] hover:text-white">Skip for now <span className="text-[#53625b]">· Chat remains unavailable until a document is indexed</span></button><button disabled={!validSources} onClick={() => setStep("configure")} className="flex h-10 items-center gap-2 rounded-lg bg-[var(--accent)] px-5 text-[10px] font-semibold text-[var(--ink-inverse)] hover:bg-[var(--accent-hover)] disabled:bg-white/[0.06] disabled:text-[#53625b]">Continue<ArrowRight className="size-3.5" /></button></div>
      </section> : null}

      {effectiveStep === "configure" ? <section className="mx-auto mt-10 max-w-3xl"><div className="text-center"><p className="text-[10px] font-semibold uppercase tracking-[.15em] text-[var(--accent)]">Step 3 of 4</p><h1 className="mt-2 text-2xl font-semibold">Prepare your documents for retrieval</h1><p className="mx-auto mt-2 max-w-xl text-[12px] leading-5 text-[#71847b]">Choose how RAGForge should parse, chunk and index your documents. Recommended settings work well for most projects.</p></div>
        <div className="mt-7 grid gap-4 md:grid-cols-[0.8fr_1.2fr]"><div className="rounded-xl border border-white/[0.09] bg-[var(--surface)] p-4"><h3 className="text-[10px] font-semibold">Knowledge sources</h3><p className="mt-1 text-[8px] text-[#64736d]">{sources.length} {sources.length === 1 ? "source" : "sources"} ready</p><div className="mt-3 space-y-2">{sources.map((source) => <div key={source.id} className="flex items-center gap-2 rounded-lg bg-white/[0.025] p-2.5"><FileText className="size-3.5 text-[var(--accent)]" /><span className="min-w-0 flex-1 truncate text-[9px]">{source.name}</span><ShieldCheck className="size-3 text-[var(--accent)]" /></div>)}</div></div>
          <div className="rounded-xl border border-white/[0.09] bg-[var(--surface)] p-4"><label className="block"><span className="text-[9px] font-medium">Chunking strategy</span><select value={chunkerId} onChange={(event) => setChunkerId(event.target.value)} className="mt-2 h-10 w-full rounded-lg border border-white/10 bg-[var(--surface-muted)] px-3 text-[10px] outline-none focus:border-[var(--border-hover)]">{chunkers.filter((chunker) => chunker.id !== "multimodal").map((chunker) => <option key={chunker.id} value={chunker.id}>{chunker.name}{chunker.default ? " · Recommended" : ""}</option>)}</select><p className="mt-1.5 text-[8px] leading-4 text-[#64736d]">{chunkers.find((chunker) => chunker.id === chunkerId)?.short_description ?? "Fast, reliable splitting for general documents and reports."}</p></label><div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-white/[0.07] bg-white/[0.018] p-3"><span className="text-[8px] text-[#64736d]">Embedding model</span><p className="mono mt-1 text-[9px]">BAAI/bge-small-en-v1.5</p></div><div className="rounded-lg border border-white/[0.07] bg-white/[0.018] p-3"><span className="text-[8px] text-[#64736d]">Retrieval strategy</span><p className="mt-1 text-[9px]">Hybrid dense + sparse</p></div></div><button onClick={() => setAdvanced((value) => !value)} className="mt-4 flex w-full items-center justify-between border-t border-white/[0.07] pt-3 text-[9px] text-[#71847b]"><span className="flex items-center gap-1.5"><Settings2 className="size-3" />Advanced ingestion information</span><ChevronDown className={cn("size-3 transition", advanced && "rotate-180")} /></button>{advanced ? <p className="mt-3 rounded-lg bg-white/[0.02] p-3 text-[8px] leading-4 text-[#64736d]">Embedding and retrieval configuration are backend defaults. The current ingestion API accepts the selected chunker but does not expose project-level embedding, OCR, or retrieval configuration.</p> : null}</div></div>
        <div className="mt-5 flex items-center justify-between"><button onClick={() => setStep("knowledge")} className="flex items-center gap-1.5 text-[9px] text-[#71847b] hover:text-white"><ArrowLeft className="size-3" />Back</button><button disabled={createKnowledgeBase.isPending} onClick={() => createKnowledgeBase.mutate()} className="flex h-10 items-center gap-2 rounded-lg bg-[var(--accent)] px-5 text-[10px] font-semibold text-[var(--ink-inverse)] hover:bg-[var(--accent-hover)] disabled:opacity-50">{createKnowledgeBase.isPending ? <LoaderCircle className="size-3.5 animate-spin" /> : <Database className="size-3.5" />}Create knowledge base</button></div>
      </section> : null}

      {effectiveStep === "processing" ? <section className="mx-auto mt-10 max-w-3xl"><div className="text-center"><p className="text-[10px] font-semibold uppercase tracking-[.15em] text-[var(--accent)]">Step 4 of 4</p><h1 className="mt-2 text-2xl font-semibold">Preparing your knowledge base</h1><p className="mx-auto mt-2 max-w-xl text-[12px] leading-5 text-[#71847b]">RAGForge is processing your documents. Follow each stage in real time.</p></div><div className="mt-7 space-y-3">{createKnowledgeBase.isPending && !effectiveRuns.length ? <div className="flex items-center gap-3 rounded-xl border border-white/[0.09] bg-[var(--surface)] p-5"><span className="flex size-9 items-center justify-center rounded-lg bg-blue-400/10 text-blue-300"><LoaderCircle className="size-4 animate-spin" /></span><div><h3 className="text-[11px] font-medium">Uploading and creating pipeline runs</h3><p className="mt-1 text-[8px] text-[#64736d]">Your sources are being validated and transferred to secure Bronze storage.</p></div></div> : null}{effectiveRuns.map((run) => <ProcessingRun key={`${run.ingestion_run_id}:${run.status}`} initialRun={run} filename={sourceNameByDocument.get(run.document_id) ?? sources.find((source) => source.kind === "file")?.name ?? "Uploaded document"} onStatus={handleRunStatus} />)}</div>{failedRun ? <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><button onClick={() => router.push("/projects")} className="text-[9px] text-[#71847b] hover:text-white">Back to project</button><div className="flex gap-2"><details className="relative"><summary className="flex h-9 cursor-pointer list-none items-center rounded-lg border border-white/10 px-3 text-[9px] text-[#93a39c]">Technical details</summary><div className="absolute bottom-11 right-0 z-20 w-80 rounded-lg border border-white/10 bg-[var(--surface-raised)] p-3 font-mono text-[8px] leading-4 text-[#93a39c] shadow-xl">Run: {failedRun.ingestion_run_id}<br />Status: {failedRun.status}<br />{failedRun.error_message}</div></details><button disabled={retry.isPending} onClick={() => retry.mutate(failedRun.ingestion_run_id)} className="flex h-9 items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 text-[9px] font-semibold text-[var(--ink-inverse)]"><RefreshCw className={cn("size-3", retry.isPending && "animate-spin")} />Retry failed stage</button></div></div> : null}</section> : null}

      {effectiveStep === "success" ? <section className="mx-auto mt-14 max-w-2xl text-center"><span className="mx-auto flex size-14 items-center justify-center rounded-2xl border border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent)]"><CheckCircle2 className="size-7" /></span><p className="mt-5 text-[10px] font-semibold uppercase tracking-[.15em] text-[var(--accent)]">Processing complete</p><h1 className="mt-2 text-2xl font-semibold">Your knowledge base is ready</h1><p className="mx-auto mt-3 max-w-lg text-[12px] leading-6 text-[#71847b]">{indexedDocuments.length || successCount || 1} {(indexedDocuments.length || successCount || 1) === 1 ? "document was" : "documents were"} successfully processed{successChunks ? ` into ${successChunks} searchable chunks` : " and can now be searched"}. You can now ask questions and verify every answer against its original source.</p><button onClick={() => router.push(`/projects/${projectId}/documents`)} className="mx-auto mt-7 flex h-11 items-center gap-2 rounded-lg bg-[var(--accent)] px-6 text-[10px] font-semibold text-[var(--ink-inverse)] hover:bg-[var(--accent-hover)]"><Sparkles className="size-4" />Open AI Workspace<ArrowRight className="size-3.5" /></button></section> : null}
    </div>
  </div>;
}
