"use client";

import {zodResolver} from "@hookform/resolvers/zod";
import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {ArrowRight, Building2, FolderKanban, Languages, LoaderCircle, Plus, X} from "lucide-react";
import Link from "next/link";
import {useState} from "react";
import {useForm} from "react-hook-form";
import {toast} from "sonner";
import {z} from "zod";
import {PageHeader} from "@/components/page-header";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {EmptyState} from "@/components/ui/empty-state";
import {Input} from "@/components/ui/input";
import {apiFetch} from "@/lib/api";
import type {Organization, Project} from "@/lib/types";
import {relativeTime} from "@/lib/utils";

const schema = z.object({
  name: z.string().trim().min(2, "Project name is required").max(120),
  description: z.string().trim().max(500).optional(),
  organization_id: z.string().optional(),
  language: z.string().min(2),
});
type Values = z.infer<typeof schema>;

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const {data: projects = [], isLoading} = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<Project[]>("/projects/"),
  });
  const {data: organizations = []} = useQuery({
    queryKey: ["organizations"],
    queryFn: () => apiFetch<Organization[]>("/organizations/"),
    enabled: creating,
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: {errors},
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {name: "", description: "", organization_id: "", language: "en"},
  });
  const createProject = useMutation({
    mutationFn: (values: Values) =>
      apiFetch<Project>("/projects/", {
        method: "POST",
        body: JSON.stringify({name: values.name, organization_id: values.organization_id || null}),
      }),
    onSuccess: async (project, values) => {
      await queryClient.invalidateQueries({queryKey: ["projects"]});
      localStorage.setItem(`ragforge:project:${project.project_id}:onboarding`, JSON.stringify({description: values.description ?? "", language: values.language}));
      reset();
      setCreating(false);
      toast.success("Project created");
      window.location.assign(`/projects/${project.project_id}/onboarding`);
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Unable to create project"),
  });

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Each project is an isolated knowledge base with its own documents, vector collection, and query history."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            New project
          </Button>
        }
      />

      {isLoading ? (
        <div
          className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          aria-label="Loading projects"
        >
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-48 animate-pulse rounded-2xl border border-[var(--border)] bg-white"
            />
          ))}
        </div>
      ) : projects.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <Card
              key={project.project_id}
              className="group p-5 transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-950/5"
            >
              <div className="flex items-start justify-between">
                <div className="flex size-11 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                  <FolderKanban className="size-5" />
                </div>
                <span className="text-xs text-[var(--ink-faint)]">
                  {relativeTime(project.updated_at)}
                </span>
              </div>
              <h2 className="mt-5 truncate text-lg font-semibold">{project.name}</h2>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--ink-muted)]">
                Upload documents, observe ingestion, and ask grounded questions
                inside this isolated project.
              </p>
              <Link
                href={`/projects/${project.project_id}/documents`}
                className="mt-5 flex items-center justify-between border-t border-[var(--border)] pt-4 text-sm font-semibold text-[var(--accent)]"
              >
                Open workspace
                <ArrowRight className="size-4 transition group-hover:translate-x-1" />
              </Link>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Create your first project to start building a searchable, observable knowledge base."
          action="Create project"
          onAction={() => setCreating(true)}
        />
      )}

      {creating ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-xl p-6 shadow-2xl sm:p-7">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-emerald-300">New project</p>
                <h2 className="mt-1 text-xl font-semibold">Create a new knowledge project</h2>
                <p className="mt-2 max-w-lg text-sm leading-6 text-[var(--ink-muted)]">
                  Create a workspace where you can upload documents, process knowledge, and ask grounded questions with traceable sources.
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setCreating(false)}>
                <X className="size-4" />
              </Button>
            </div>
            <form
              className="mt-7"
              onSubmit={handleSubmit((values) => createProject.mutate(values))}
            >
              <label className="block">
                <span className="mb-2 block text-sm font-medium">Project name</span>
                <Input autoFocus placeholder="Product knowledge base" {...register("name")} />
                {errors.name ? (
                  <span className="mt-1.5 block text-xs text-[var(--danger)]">
                    {errors.name.message}
                  </span>
                ) : null}
              </label>
              <label className="mt-4 block">
                <span className="mb-2 block text-sm font-medium">Project description <span className="font-normal text-[var(--ink-faint)]">(optional)</span></span>
                <textarea className="min-h-20 w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3.5 py-2.5 text-sm outline-none placeholder:text-[var(--ink-faint)] focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]" placeholder="What knowledge will this project contain?" {...register("description")} />
              </label>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 flex items-center gap-1.5 text-sm font-medium"><Building2 className="size-3.5 text-[var(--ink-faint)]" />Organization</span>
                  <select className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 text-sm outline-none focus:border-[var(--accent)]" {...register("organization_id")}>
                    <option value="">Personal workspace</option>
                    {organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.name}</option>)}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-2 flex items-center gap-1.5 text-sm font-medium"><Languages className="size-3.5 text-[var(--ink-faint)]" />Default language</span>
                  <select className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 text-sm outline-none focus:border-[var(--accent)]" {...register("language")}>
                    <option value="en">English</option><option value="fr">French</option><option value="ar">Arabic</option><option value="es">Spanish</option><option value="de">German</option>
                  </select>
                </label>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createProject.isPending}>
                  {createProject.isPending ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Plus className="size-4" />
                  )}
                  Create Project
                </Button>
              </div>
            </form>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
