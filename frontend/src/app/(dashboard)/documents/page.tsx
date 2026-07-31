"use client";

import {useMutation, useQueryClient} from "@tanstack/react-query";
import {FileStack, Search} from "lucide-react";
import {useMemo, useState} from "react";
import {toast} from "sonner";
import {ConfirmDeleteDialog} from "@/components/confirm-delete-dialog";
import {DocumentList} from "@/components/document-list";
import {PageHeader} from "@/components/page-header";
import {EmptyState} from "@/components/ui/empty-state";
import {ErrorState} from "@/components/ui/error-state";
import {Input} from "@/components/ui/input";
import {LoadingState} from "@/components/ui/loading-state";
import {useWorkspaceOverview} from "@/hooks/use-workspace-overview";
import {apiFetch} from "@/lib/api";
import type {Document} from "@/lib/types";

export default function DocumentsPage() {
  const overview = useWorkspaceOverview({documents: true});
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<Document | null>(null);
  const filtered = useMemo(() => overview.documents.filter((document) => (status === "all" || document.status === status) && (document.filename ?? "").toLowerCase().includes(search.toLowerCase())), [overview.documents, search, status]);
  const remove = useMutation({mutationFn: (document: Document) => apiFetch(`/documents/${document.document_id}`, {method: "DELETE"}), onSuccess: async (_, document) => {await queryClient.invalidateQueries({queryKey: ["documents", document.project_id]}); setSelected(null); toast.success("Document deleted");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to delete document")});
  return <div className="mx-auto max-w-7xl space-y-6"><PageHeader eyebrow="Sources" title="Sources" description="Browse files, URLs, drives, and dataset-like sources across projects. Open a source to inspect its immutable version lineage and runs." />
    <div className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-[#0a1511] p-3 sm:flex-row"><label className="relative flex-1"><span className="sr-only">Search documents</span><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#64736d]" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search filenames" /></label><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-lg border border-white/[0.08] bg-[var(--surface-muted)] px-3 text-xs" aria-label="Filter documents by status"><option value="all">All statuses</option>{["landed","queued","running","indexed","failed"].map((value) => <option key={value} value={value}>{value}</option>)}</select></div>
    {overview.pending ? <LoadingState label="Loading sources" rows={5} /> : overview.error ? <ErrorState title="Sources could not be loaded" description="At least one owned project returned an error while loading its sources." onRetry={() => void overview.refetch()} /> : filtered.length ? <DocumentList items={filtered} onDelete={setSelected} /> : <EmptyState icon={FileStack} title={search || status !== "all" ? "No matching sources" : "No sources yet"} description={search || status !== "all" ? "Try a different filename or status." : "Open a project and upload a source to begin."} />}
    {selected ? <ConfirmDeleteDialog open name={selected.filename ?? selected.document_id} title={`Delete ${selected.filename ?? "document"}?`} consequences="The document and its indexed Qdrant chunks will be removed. Individual version rollback or recovery is not supported." isPending={remove.isPending} onClose={() => setSelected(null)} onConfirm={() => remove.mutate(selected)} /> : null}
  </div>;
}
