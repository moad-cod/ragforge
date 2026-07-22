"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {FileStack, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, X} from "lucide-react";
import {useCallback, useEffect, useMemo, useState} from "react";
import {useSearchParams} from "next/navigation";
import {toast} from "sonner";
import {apiFetch} from "@/lib/api";
import type {Chunker, Document as ApiDocument, IngestionRun, Project, RetrievalTrace} from "@/lib/types";
import {ConfirmDeleteDialog} from "@/components/confirm-delete-dialog";
import {AssistantPanel} from "@/components/workspace/assistant-panel";
import {DocumentPanel} from "@/components/workspace/document-panel";
import {SourceInspector, type InspectorTab} from "@/components/workspace/source-inspector";
import type {WorkspaceDocument} from "@/components/workspace/workspace-data";

function enrichDocument(document: ApiDocument): WorkspaceDocument {
  return {
    ...document,
    size: "",
    pages: 0,
    chunks: 0,
    version: 0,
    owner: "",
  };
}

function useStoredNumber(key: string, fallback: number) {
  const [value, setValue] = useState(() => {
    if (typeof window === "undefined") return fallback;
    const stored = Number(localStorage.getItem(key));
    return Number.isFinite(stored) && stored > 0 ? stored : fallback;
  });
  const update = useCallback((next: number) => { setValue(next); localStorage.setItem(key, String(next)); }, [key]);
  return [value, update] as const;
}

export function KnowledgeWorkspace({projectId}: {projectId: string}) {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const initialDocumentId = searchParams.get("document") ?? "";
  const {data = [], isError} = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => apiFetch<ApiDocument[]>(`/documents/?project_id=${projectId}`),
    retry: 0,
  });
  const {data: project} = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
  });
  const {data: runs = []} = useQuery({queryKey: ["ingestion-runs", projectId], queryFn: () => apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${projectId}&limit=100`), refetchInterval: 10_000});
  const {data: chunkers = []} = useQuery({queryKey: ["chunkers"], queryFn: () => apiFetch<Chunker[]>("/chunkers")});
  const projectName = project?.name ?? "Project workspace";
  const documents = useMemo(() => data.map(enrichDocument), [data]);
  const [selectedDocumentId, setSelectedDocumentId] = useState(initialDocumentId);
  const [selectedIds, setSelectedIds] = useState<string[]>(initialDocumentId ? [initialDocumentId] : []);
  const [citation, setCitation] = useState<RetrievalTrace | undefined>();
  const [tab, setTab] = useState<InspectorTab>("Content");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [mobileDocuments, setMobileDocuments] = useState(false);
  const [mobileInspector, setMobileInspector] = useState(false);
  const [leftWidth, setLeftWidth] = useStoredNumber("ragforge:left-panel", 332);
  const [rightWidth, setRightWidth] = useStoredNumber("ragforge:right-panel", 520);
  const [deleting, setDeleting] = useState<WorkspaceDocument | null>(null);
  const autoSelectedDocument = documents.find((document) => document.status === "indexed");
  const activeDocument = documents.find((doc) => doc.document_id === selectedDocumentId) ?? autoSelectedDocument;
  const effectiveSelectedIds = selectedIds.length || selectedDocumentId ? selectedIds : autoSelectedDocument ? [autoSelectedDocument.document_id] : [];

  useEffect(() => {
    if (isError) toast.error("Documents could not be loaded from the backend.", {id: "documents-error"});
  }, [isError]);

  function startResize(side: "left" | "right", startEvent: React.PointerEvent) {
    startEvent.preventDefault();
    const startX = startEvent.clientX;
    const startWidth = side === "left" ? leftWidth : rightWidth;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    const move = (event: PointerEvent) => {
      const delta = event.clientX - startX;
      if (side === "left") setLeftWidth(Math.min(420, Math.max(280, startWidth + delta)));
      else setRightWidth(Math.min(680, Math.max(390, startWidth - delta)));
    };
    const stop = () => {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id) ? [] : [id]);
  }

  function openCitation(source: RetrievalTrace) {
    if (source.document_id) setSelectedDocumentId(source.document_id);
    setCitation(source);
    setTab("Content");
    setRightOpen(true);
    setMobileInspector(true);
  }

  async function upload(file: File, chunkerId: string) {
    const form = new FormData();
    form.set("project_id", projectId);
    form.set("chunker", chunkerId);
    form.set("file", file);
    try {
      await apiFetch<{ingestion_run_id: string}>("/ingest/file", {method: "POST", body: form});
      await Promise.all([
        queryClient.invalidateQueries({queryKey: ["documents", projectId]}),
        queryClient.invalidateQueries({queryKey: ["ingestion-runs", projectId]}),
      ]);
      toast.success("Upload accepted. Ingestion is now running.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed. The document was not added.");
      throw error;
    }
  }

  async function addUrl(url: string, chunkerId: string) {
    try {await apiFetch("/ingest/url", {method: "POST", body: JSON.stringify({project_id: projectId, chunker: chunkerId, url})}); await queryClient.invalidateQueries({queryKey: ["documents", projectId]}); toast.success("URL indexed successfully");}
    catch (error) {toast.error(error instanceof Error ? error.message : "URL ingestion failed"); throw error;}
  }

  async function addGDrive(fileId: string, accessToken: string, chunkerId: string) {
    try {await apiFetch("/ingest/gdrive", {method: "POST", body: JSON.stringify({project_id: projectId, chunker: chunkerId, file_id: fileId, access_token: accessToken})}); await queryClient.invalidateQueries({queryKey: ["documents", projectId]}); toast.success("Google Drive file indexed successfully");}
    catch (error) {toast.error(error instanceof Error ? error.message : "Google Drive ingestion failed"); throw error;}
  }

  const removeDocument = useMutation({mutationFn: (document: WorkspaceDocument) => apiFetch(`/documents/${document.document_id}`, {method: "DELETE"}), onSuccess: async (_, document) => {await queryClient.invalidateQueries({queryKey: ["documents", projectId]}); if (selectedDocumentId === document.document_id) setSelectedDocumentId(""); setSelectedIds((current) => current.filter((id) => id !== document.document_id)); setDeleting(null); toast.success("Document deleted");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to delete document")});
  const retryRun = useMutation({mutationFn: (run: IngestionRun) => apiFetch<IngestionRun>(`/ingest/runs/${run.ingestion_run_id}/retry`, {method: "POST"}), onSuccess: async () => {await queryClient.invalidateQueries({queryKey: ["ingestion-runs", projectId]}); toast.success("Retry queued");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to retry ingestion")});

  return <div className="relative flex h-full min-w-0 overflow-hidden">
    <div className="hidden h-full shrink-0 lg:block" style={{width: leftOpen ? leftWidth : 0}}>
      {leftOpen ? <DocumentPanel projectId={projectId} projectName={projectName} documents={documents} runs={runs} chunkers={chunkers} selectedIds={effectiveSelectedIds} selectedDocumentId={activeDocument?.document_id ?? ""} onSelectDocument={(id) => {setSelectedDocumentId(id); setCitation(undefined); setRightOpen(true);}} onToggleSelected={toggleSelected} onUpload={upload} onUrl={addUrl} onGDrive={addGDrive} onDelete={setDeleting} onRetry={(run) => retryRun.mutate(run)} /> : null}
    </div>
    {leftOpen ? <div role="separator" aria-label="Resize document panel" aria-orientation="vertical" onPointerDown={(event) => startResize("left", event)} className="relative z-30 hidden w-px shrink-0 cursor-col-resize bg-white/[0.08] transition hover:bg-emerald-400/60 lg:block"><span className="absolute inset-y-0 -left-1.5 w-3" /></div> : null}

    <div className="relative min-w-[320px] flex-1">
      <AssistantPanel
        projectId={projectId}
        projectName={projectName}
        documents={documents}
        selectedIds={effectiveSelectedIds}
        onRemoveSelected={toggleSelected}
        onCitation={openCitation}
        onOpenTrace={() => {setTab("Retrieval Trace"); setRightOpen(true); setMobileInspector(true);}}
      />
      <div className="absolute left-2 top-[57px] z-20 flex gap-1">
        <button onClick={() => {if (window.innerWidth < 1024) setMobileDocuments(true); else setLeftOpen((value) => !value);}} title={leftOpen ? "Collapse documents" : "Open documents"} className="flex size-7 items-center justify-center rounded-lg border border-white/[0.08] bg-[#0e1c17]/95 text-[#64736d] shadow-lg hover:text-white">{leftOpen ? <PanelLeftClose className="size-3.5" /> : <PanelLeftOpen className="size-3.5" />}</button>
      </div>
      <button onClick={() => setMobileDocuments(true)} className="absolute bottom-14 left-3 z-30 flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-[#13251e] px-2.5 text-[9px] text-[#a9b7b0] shadow-lg lg:hidden"><FileStack className="size-3" />Documents</button>
      <button disabled={!activeDocument} onClick={() => setMobileInspector(true)} className="absolute bottom-14 right-3 z-30 flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-[#13251e] px-2.5 text-[9px] text-[#a9b7b0] shadow-lg disabled:hidden xl:hidden"><PanelRightOpen className="size-3" />Sources</button>
    </div>

    {rightOpen && activeDocument ? <div role="separator" aria-label="Resize source inspector" aria-orientation="vertical" onPointerDown={(event) => startResize("right", event)} className="relative z-30 hidden w-px shrink-0 cursor-col-resize bg-white/[0.08] transition hover:bg-emerald-400/60 xl:block"><span className="absolute inset-y-0 -left-1.5 w-3" /></div> : null}
    <div className="relative hidden h-full shrink-0 xl:block" style={{width: rightOpen && activeDocument ? rightWidth : 0}}>
      {rightOpen && activeDocument ? <SourceInspector document={activeDocument} citation={citation} activeTab={tab} onTabChange={setTab} /> : null}
      <button onClick={() => setRightOpen(false)} title="Collapse source inspector" className="absolute -left-8 top-2 z-40 flex size-7 items-center justify-center rounded-lg border border-white/[0.08] bg-[#0e1c17] text-[#64736d] hover:text-white"><PanelRightClose className="size-3.5" /></button>
    </div>
    {!rightOpen && activeDocument ? <button onClick={() => setRightOpen(true)} title="Open source inspector" className="absolute right-2 top-[57px] z-40 hidden size-7 items-center justify-center rounded-lg border border-white/[0.08] bg-[#0e1c17] text-[#64736d] hover:text-white xl:flex"><PanelRightOpen className="size-3.5" /></button> : null}

    {mobileDocuments ? <div className="fixed inset-0 z-[80] lg:hidden"><button aria-label="Close documents" className="absolute inset-0 bg-black/65 backdrop-blur-sm" onClick={() => setMobileDocuments(false)} /><div className="absolute inset-y-0 left-0 w-[88%] max-w-[360px] border-r border-white/10 shadow-2xl"><DocumentPanel projectId={projectId} projectName={projectName} documents={documents} runs={runs} chunkers={chunkers} selectedIds={effectiveSelectedIds} selectedDocumentId={activeDocument?.document_id ?? ""} onSelectDocument={(id) => {setSelectedDocumentId(id); setMobileDocuments(false);}} onToggleSelected={toggleSelected} onUpload={upload} onUrl={addUrl} onGDrive={addGDrive} onDelete={setDeleting} onRetry={(run) => retryRun.mutate(run)} /><button onClick={() => setMobileDocuments(false)} className="absolute right-2 top-2 flex size-7 items-center justify-center rounded-lg bg-white/5"><X className="size-3.5" /></button></div></div> : null}
    {mobileInspector && activeDocument ? <div className="fixed inset-0 z-[85] xl:hidden"><button aria-label="Close source inspector" className="absolute inset-0 bg-black/65 backdrop-blur-sm" onClick={() => setMobileInspector(false)} /><div className="absolute inset-y-0 right-0 w-full max-w-[620px] border-l border-white/10 shadow-2xl"><SourceInspector document={activeDocument} citation={citation} activeTab={tab} onTabChange={setTab} onClose={() => setMobileInspector(false)} /></div></div> : null}
    {deleting ? <ConfirmDeleteDialog open name={deleting.filename ?? deleting.document_id} title={`Delete ${deleting.filename ?? "document"}?`} consequences="The document, its version lineage, and indexed chunks will no longer be available. Query audit metadata may remain." isPending={removeDocument.isPending} onClose={() => setDeleting(null)} onConfirm={() => removeDocument.mutate(deleting)} /> : null}
  </div>;
}
