"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {Database, LoaderCircle, Save, Settings, Trash2} from "lucide-react";
import {useRouter} from "next/navigation";
import {use, useState} from "react";
import {toast} from "sonner";
import {ConfirmDeleteDialog} from "@/components/confirm-delete-dialog";
import {PageHeader} from "@/components/page-header";
import {Button} from "@/components/ui/button";
import {ErrorState} from "@/components/ui/error-state";
import {Input} from "@/components/ui/input";
import {LoadingState} from "@/components/ui/loading-state";
import {apiFetch} from "@/lib/api";
import type {Document, Project} from "@/lib/types";

export default function ProjectSettingsPage({params}: {params: Promise<{projectId: string}>}) {
  const {projectId} = use(params);
  const router = useRouter(); const queryClient = useQueryClient(); const [name, setName] = useState<string | null>(null); const [confirm, setConfirm] = useState(false);
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`)});
  const documents = useQuery({queryKey: ["documents", projectId], queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`)});
  const effectiveName = name ?? project.data?.name ?? "";
  const rename = useMutation({mutationFn: () => apiFetch<Project>(`/projects/${projectId}`, {method: "PATCH", body: JSON.stringify({name: effectiveName})}), onSuccess: async () => {setName(null); await Promise.all([queryClient.invalidateQueries({queryKey: ["project", projectId]}), queryClient.invalidateQueries({queryKey: ["projects"]})]); toast.success("Project settings saved");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to update project")});
  const remove = useMutation({mutationFn: () => apiFetch(`/projects/${projectId}`, {method: "DELETE"}), onSuccess: async () => {await queryClient.invalidateQueries({queryKey: ["projects"]}); toast.success("Project deleted"); router.replace("/projects");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to delete project")});
  if (project.isLoading) return <LoadingState label="Loading project settings" rows={4} />;
  if (project.isError || !project.data) return <ErrorState title="Project settings could not be loaded" description="The project may not exist or may belong to another tenant." onRetry={() => void project.refetch()} />;
  return <div className="mx-auto max-w-4xl space-y-6"><PageHeader eyebrow={project.data.name} title="Project settings" description="Update settings supported by the current project API. Collection identity remains immutable to preserve indexed data." />
    <section className="rounded-xl border border-white/[0.08] bg-[#0a1511] p-5"><div className="flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300"><Settings className="size-4" /></span><div><h2 className="text-sm font-semibold">General</h2><p className="mt-0.5 text-[9px] text-[#64736d]">The backend currently supports project-name updates.</p></div></div><label className="mt-5 block"><span className="mb-2 block text-xs font-medium">Project name</span><Input value={effectiveName} onChange={(event) => setName(event.target.value)} /></label><div className="mt-5 flex justify-end"><Button disabled={rename.isPending || effectiveName.trim().length < 2 || effectiveName === project.data.name} onClick={() => rename.mutate()}>{rename.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}Save name</Button></div></section>
    <section className="rounded-xl border border-white/[0.08] bg-[#0a1511] p-5"><div className="flex items-center gap-3"><Database className="size-4 text-[#64736d]" /><div><h2 className="text-sm font-semibold">Storage identity</h2><p className="mt-0.5 text-[9px] text-[#64736d]">Read-only values assigned by the backend.</p></div></div><dl className="mt-5 space-y-3 text-[10px]"><div className="grid gap-1 sm:grid-cols-[150px_1fr]"><dt className="text-[#64736d]">Project ID</dt><dd className="mono break-all text-[#a9b7b0]">{project.data.project_id}</dd></div><div className="grid gap-1 sm:grid-cols-[150px_1fr]"><dt className="text-[#64736d]">Qdrant collection</dt><dd className="mono break-all text-[#a9b7b0]">{project.data.qdrant_collection}</dd></div></dl></section>
    <section className="rounded-xl border border-red-400/15 bg-red-400/[0.025] p-5"><h2 className="text-sm font-semibold text-red-200">Danger zone</h2><p className="mt-2 text-[10px] leading-5 text-[#83948c]">Deleting this project removes {documents.data?.length ?? "all"} documents and its Qdrant collections. Query history will no longer be accessible through the project.</p><Button className="mt-4" variant="danger" onClick={() => setConfirm(true)}><Trash2 className="size-4" />Delete project</Button></section>
    <ConfirmDeleteDialog open={confirm} onClose={() => setConfirm(false)} name={project.data.name} title={`Delete ${project.data.name}?`} consequences={`${documents.data?.length ?? "All"} documents, indexed chunks, and accessible query history will be affected.`} isPending={remove.isPending} onConfirm={() => remove.mutate()} />
  </div>;
}
