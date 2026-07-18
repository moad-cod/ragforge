"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {
  FileText,
  LoaderCircle,
  Search,
  Trash2,
  UploadCloud,
} from "lucide-react";
import {useMemo, useRef, useState} from "react";
import {toast} from "sonner";
import {IngestionCard} from "@/components/ingestion-card";
import {PageHeader} from "@/components/page-header";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {EmptyState} from "@/components/ui/empty-state";
import {Input} from "@/components/ui/input";
import {apiFetch} from "@/lib/api";
import type {Chunker, Document, IngestionRun, Project} from "@/lib/types";
import {cn, relativeTime} from "@/lib/utils";

function statusTone(status: string) {
  if (status === "indexed") return "success" as const;
  if (status === "failed") return "danger" as const;
  if (["processing", "chunked", "embedded", "landed"].includes(status))
    return "info" as const;
  return "neutral" as const;
}

export function DocumentsWorkspace({projectId}: {projectId: string}) {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [chunkerId, setChunkerId] = useState("paragraph");
  const [dragging, setDragging] = useState(false);
  const [search, setSearch] = useState("");
  const {data: project} = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
  });
  const {data: documents = [], isLoading} = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`),
  });
  const {data: runs = []} = useQuery({
    queryKey: ["ingestion-runs", projectId],
    queryFn: () =>
      apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${projectId}&limit=30`),
    refetchInterval: 10_000,
  });
  const {data: chunkers = []} = useQuery({
    queryKey: ["chunkers"],
    queryFn: () => apiFetch<Chunker[]>("/chunkers"),
  });
  const filteredDocuments = useMemo(
    () =>
      documents.filter((document) =>
        (document.filename ?? "").toLowerCase().includes(search.toLowerCase()),
      ),
    [documents, search],
  );
  const documentById = useMemo(
    () => new Map(documents.map((document) => [document.document_id, document])),
    [documents],
  );

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a document first");
      const form = new FormData();
      form.set("project_id", projectId);
      form.set("chunker", chunkerId);
      form.set("file", file);
      return apiFetch<{
        document_id: string;
        document_version_id: string;
        ingestion_run_id: string;
        status: string;
      }>("/ingest/file", {
        method: "POST",
        body: form,
      });
    },
    onSuccess: async () => {
      setFile(null);
      await Promise.all([
        queryClient.invalidateQueries({queryKey: ["documents", projectId]}),
        queryClient.invalidateQueries({queryKey: ["ingestion-runs", projectId]}),
      ]);
      toast.success("Document accepted. Ingestion is now running.");
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Upload failed"),
  });
  const removeDocument = useMutation({
    mutationFn: (documentId: string) =>
      apiFetch(`/documents/${documentId}`, {method: "DELETE"}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({queryKey: ["documents", projectId]});
      toast.success("Document removed");
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Unable to remove document"),
  });

  const activeRuns = runs.filter((run) => run.status !== "indexed");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={project?.name ?? "Project"}
        title="Documents"
        description="Upload source material and follow the durable ingestion pipeline from Bronze storage to the searchable index."
      />

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-5 sm:p-6">
          <div className="mb-5">
            <h2 className="text-lg font-semibold">Add knowledge</h2>
            <p className="mt-1 text-sm text-[var(--ink-muted)]">
              Files are accepted immediately, then processed asynchronously.
            </p>
          </div>
          <button
            className={cn(
              "flex min-h-48 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 text-center transition",
              dragging
                ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                : "border-[var(--border-strong)] bg-[var(--surface-muted)] hover:border-indigo-300",
            )}
            onClick={() => fileInput.current?.click()}
            onDragEnter={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              setFile(event.dataTransfer.files[0] ?? null);
            }}
          >
            <div className="flex size-12 items-center justify-center rounded-2xl bg-white text-[var(--accent)] shadow-sm">
              <UploadCloud className="size-6" />
            </div>
            <p className="mt-4 text-sm font-semibold">
              {file ? file.name : "Drop a document here or browse"}
            </p>
            <p className="mt-1 text-xs text-[var(--ink-muted)]">
              PDF, DOCX, XLSX, PPTX, CSV, HTML, Markdown, or text · max 25 MB
            </p>
          </button>
          <input
            ref={fileInput}
            className="hidden"
            type="file"
            accept=".pdf,.docx,.xlsx,.pptx,.csv,.html,.htm,.md,.txt"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />

          <div className="mt-5 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <label>
              <span className="mb-2 block text-sm font-medium">
                Chunking strategy
              </span>
              <select
                className="h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 text-sm outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
                value={chunkerId}
                onChange={(event) => setChunkerId(event.target.value)}
              >
                {chunkers
                  .filter((chunker) => chunker.id !== "multimodal")
                  .map((chunker) => (
                    <option key={chunker.id} value={chunker.id}>
                      {chunker.name}
                      {chunker.is_beta ? " · beta" : ""}
                    </option>
                  ))}
              </select>
              <p className="mt-1.5 text-xs text-[var(--ink-faint)]">
                {chunkers.find((chunker) => chunker.id === chunkerId)
                  ?.short_description ?? "Choose how document text is divided."}
              </p>
            </label>
            <Button
              className="sm:mb-5"
              disabled={!file || upload.isPending}
              onClick={() => upload.mutate()}
            >
              {upload.isPending ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <UploadCloud className="size-4" />
              )}
              Upload document
            </Button>
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-semibold">Ingestion activity</h2>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            Live stages reconnect from durable PostgreSQL state after refresh.
          </p>
          <div className="mt-5 space-y-3">
            {activeRuns.length ? (
              activeRuns.slice(0, 3).map((run) => (
                <IngestionCard
                  key={`${run.ingestion_run_id}:${run.status}`}
                  initialRun={run}
                  document={documentById.get(run.document_id)}
                  projectId={projectId}
                />
              ))
            ) : (
              <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl bg-[var(--surface-muted)] px-5 text-center">
                <FileText className="size-6 text-[var(--ink-faint)]" />
                <p className="mt-3 text-sm font-medium">No active ingestion runs</p>
                <p className="mt-1 text-xs text-[var(--ink-muted)]">
                  New uploads will appear here immediately.
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      <section>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Knowledge base</h2>
            <p className="mt-1 text-sm text-[var(--ink-muted)]">
              {documents.length} {documents.length === 1 ? "document" : "documents"}
            </p>
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--ink-faint)]" />
            <Input
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search documents"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="h-64 animate-pulse rounded-2xl bg-white" />
        ) : filteredDocuments.length ? (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-[var(--border)] bg-[var(--surface-muted)] text-xs uppercase tracking-wider text-[var(--ink-faint)]">
                  <tr>
                    <th className="px-5 py-3.5 font-semibold">Document</th>
                    <th className="px-5 py-3.5 font-semibold">Type</th>
                    <th className="px-5 py-3.5 font-semibold">Status</th>
                    <th className="px-5 py-3.5 font-semibold">Updated</th>
                    <th className="px-5 py-3.5 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {filteredDocuments.map((document) => (
                    <tr key={document.document_id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex size-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                            <FileText className="size-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="max-w-sm truncate font-medium">
                              {document.filename || "Untitled document"}
                            </p>
                            <p className="mt-0.5 truncate font-mono text-[10px] text-[var(--ink-faint)]">
                              {document.document_id}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 uppercase text-[var(--ink-muted)]">
                        {document.extension?.replace(".", "") || document.source_type || "—"}
                      </td>
                      <td className="px-5 py-4">
                        <Badge tone={statusTone(document.status)}>
                          {document.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-4 text-[var(--ink-muted)]">
                        {relativeTime(document.updated_at)}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${document.filename}`}
                          disabled={removeDocument.isPending}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete ${document.filename ?? "this document"} and its indexed chunks?`,
                              )
                            ) {
                              removeDocument.mutate(document.document_id);
                            }
                          }}
                        >
                          <Trash2 className="size-4 text-[var(--danger)]" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ) : (
          <EmptyState
            icon={FileText}
            title={search ? "No matching documents" : "No documents yet"}
            description={
              search
                ? "Try a different document name."
                : "Upload your first source document to begin building this project's knowledge base."
            }
            action={search ? undefined : "Choose a document"}
            onAction={search ? undefined : () => fileInput.current?.click()}
          />
        )}
      </section>
    </div>
  );
}
