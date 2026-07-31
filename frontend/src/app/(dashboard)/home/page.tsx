"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {AlertTriangle, ArrowRight, BookOpen, CheckCircle2, Database, FolderKanban, LoaderCircle, Plus, Sparkles, Workflow} from "lucide-react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {MetricCard} from "@/components/metric-card";
import {PageHeader} from "@/components/page-header";
import {ProjectForm, type ProjectFormValues} from "@/components/project-form";
import {StatusBadge} from "@/components/status-badge";
import {Button} from "@/components/ui/button";
import {Dialog} from "@/components/ui/dialog";
import {ErrorState} from "@/components/ui/error-state";
import {LoadingState} from "@/components/ui/loading-state";
import {useWorkspaceOverview} from "@/hooks/use-workspace-overview";
import {apiFetch} from "@/lib/api";
import type {Chunker, IngestionRun, Organization, Project} from "@/lib/types";
import {relativeTime} from "@/lib/utils";
import {useState} from "react";

const experimentSteps = [
  "Create a project",
  "Add documents or a BEIR evaluation dataset",
  "Choose a RAG strategy",
  "Select Airflow or Celery",
  "Run, evaluate, and compare the experiment",
];

function SectionEmpty({title, description}: {title: string; description: string}) {
  return <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-5 text-sm text-[var(--ink-muted)]">
    <p className="font-medium text-[var(--ink-secondary)]">{title}</p>
    <p className="mt-1 max-w-xl leading-6">{description}</p>
  </div>;
}

export default function HomePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const overview = useWorkspaceOverview({documents: true, runs: true, history: true});
  const organizationsQuery = useQuery({queryKey: ["organizations"], queryFn: () => apiFetch<Organization[]>("/organizations/"), enabled: createOpen});
  const chunkersQuery = useQuery({queryKey: ["chunkers"], queryFn: () => apiFetch<Chunker[]>("/chunkers"), enabled: createOpen});
  const create = useMutation({
    mutationFn: (values: ProjectFormValues) => apiFetch<Project>("/projects/", {method: "POST", body: JSON.stringify({name: values.name, organization_id: values.organization_id || null})}),
    onSuccess: async (project, values) => {
      localStorage.setItem(`ragforge:project:${project.project_id}:chunker`, values.chunker);
      await queryClient.invalidateQueries({queryKey: ["projects"]});
      setCreateOpen(false);
      router.push(`/projects/${project.project_id}/onboarding`);
    },
  });
  if (overview.pending) return <LoadingState label="Loading home dashboard" rows={6} />;
  if (overview.error) return <ErrorState title="Workspace summary could not be loaded" description="One or more control-plane endpoints returned an error." onRetry={() => void overview.refetch()} />;

  const indexed = overview.documents.filter((document) => document.status === "indexed").length;
  const running = overview.runs.filter((run) => !["indexed", "failed", "cancelled"].includes(run.status));
  const attentionRuns = overview.runs.filter((run) => ["failed", "cancelled"].includes(run.status));
  const recentProjects = [...overview.projects].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 5);
  const isEmptyWorkspace = overview.projects.length === 0;

  const createAction = <Button className="w-full sm:w-auto" disabled={create.isPending} onClick={() => setCreateOpen(true)}>{create.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}Create project</Button>;

  return <div className="mx-auto max-w-6xl space-y-6">
    <PageHeader eyebrow="Workspace" title="Home" description="A focused starting point for project-scoped RAG experiments, source readiness, pipeline health, and comparison work." actions={createAction} />

    {isEmptyWorkspace ? <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6">
      <div className="max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-[.14em] text-[var(--accent)]">Guided workflow</p>
        <h2 className="mt-2 text-xl font-semibold text-[var(--ink)]">Create your first RAG experiment</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--ink-secondary)]">Build and evaluate a retrieval pipeline through one guided workflow.</p>
      </div>
      <ol className="mt-5 grid gap-2 md:grid-cols-5">
        {experimentSteps.map((step, index) => <li key={step} className="rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-3">
          <span className="flex size-7 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent)]">{index + 1}</span>
          <p className="mt-3 text-sm font-medium leading-5 text-[var(--ink-secondary)]">{step}</p>
        </li>)}
      </ol>
      <div className="mt-6 flex flex-col gap-2 sm:flex-row">
        <Button className="w-full sm:w-auto" disabled={create.isPending} onClick={() => setCreateOpen(true)}>{create.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}Create project</Button>
        <Link href="/experiments" className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] px-4 text-sm font-medium text-[var(--ink-secondary)] transition hover:bg-[var(--surface-hover)] hover:text-[var(--ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] sm:w-auto"><BookOpen className="size-4" />Learn how experiments work</Link>
      </div>
    </section> : <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Active projects" value={overview.projects.length} detail="Project workspaces available" icon={FolderKanban} />
        <MetricCard label="Indexed sources" value={`${indexed}/${overview.documents.length}`} detail="Ready for retrieval" icon={Database} />
        <MetricCard label="Running jobs" value={running.length} detail="Non-terminal pipeline runs" icon={Workflow} />
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="flex items-center justify-between"><span className="text-sm font-medium text-[var(--ink-muted)]">Completed experiments</span><Sparkles className="size-4 text-[var(--accent)]" /></div>
          <p className="mt-3 text-sm font-semibold text-[var(--ink-secondary)]">Not connected</p>
          <p className="mt-1 text-xs leading-5 text-[var(--ink-faint)]">Waiting for a real experiment API.</p>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="flex items-center justify-between border-b border-[var(--border)] p-4"><div><h2 className="text-base font-semibold">Recent projects</h2><p className="mt-1 text-sm text-[var(--ink-muted)]">Continue from overview, sources, playground, pipelines, or evaluation.</p></div><Link href="/projects" className="text-sm font-medium text-[var(--accent)] hover:text-[var(--accent-hover)]">View all</Link></div>
          {recentProjects.length ? <div className="divide-y divide-[var(--border)]">{recentProjects.map((project) => <Link key={project.project_id} href={`/projects/${project.project_id}/overview`} className="flex items-center gap-3 p-4 transition hover:bg-[var(--surface-hover)]"><span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]"><FolderKanban className="size-4" /></span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{project.name}</span><span className="mt-1 block text-xs text-[var(--ink-faint)]">Updated {relativeTime(project.updated_at)}</span></span><ArrowRight className="size-4 text-[var(--ink-faint)]" /></Link>)}</div> : <div className="p-4"><SectionEmpty title="No recent projects" description="Create a project to start assembling sources and running playground checks." /></div>}
        </section>

        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="flex items-center justify-between border-b border-[var(--border)] p-4"><div><h2 className="text-base font-semibold">Runs requiring attention</h2><p className="mt-1 text-sm text-[var(--ink-muted)]">Failed or cancelled jobs that may need retry or inspection.</p></div><Link href="/runs" className="text-sm font-medium text-[var(--accent)] hover:text-[var(--accent-hover)]">View runs</Link></div>
          {attentionRuns.length ? <div className="divide-y divide-[var(--border)]">{attentionRuns.slice(0, 5).map((run) => {
            const runProject = (run as IngestionRun & {project?: Project}).project;
            const projectId = runProject?.project_id;
            const href = projectId ? `/projects/${projectId}/runs/${run.ingestion_run_id}` : "/runs";
            return <Link key={run.ingestion_run_id} href={href} className="flex items-center gap-3 p-4 transition hover:bg-[var(--surface-hover)]"><AlertTriangle className="size-4 shrink-0 text-[var(--warning)]" /><span className="min-w-0 flex-1"><span className="mono block truncate text-xs text-[var(--ink-secondary)]">{run.ingestion_run_id}</span><span className="mt-1 block truncate text-xs text-[var(--ink-faint)]">{runProject?.name ?? "Project unavailable"} · {relativeTime(run.created_at)}</span></span><StatusBadge status={run.status} /></Link>;
          })}</div> : <div className="p-4"><SectionEmpty title="No runs need attention" description="Failed and cancelled pipeline runs will appear here when the backend reports them." /></div>}
        </section>
      </div>

      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2"><CheckCircle2 className="size-4 text-[var(--accent)]" /><h2 className="text-base font-semibold">Recent experiments</h2></div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ink-muted)]">Experiment records are planned for the benchmark product, but no backend endpoint is available yet. This section is intentionally empty instead of showing synthetic experiment results.</p>
          </div>
          <Link href="/experiments" className="inline-flex h-9 items-center justify-center rounded-lg border border-[var(--border)] px-3 text-sm font-medium text-[var(--ink-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]">Open experiments</Link>
        </div>
      </section>
    </>}

    <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="Create project" description="Create an isolated workspace and choose the initial upload preference.">
      <ProjectForm organizations={organizationsQuery.data ?? []} chunkers={chunkersQuery.data ?? []} isPending={create.isPending} onCancel={() => setCreateOpen(false)} onSubmit={(values) => create.mutate(values)} />
      {create.isError ? <p className="mt-3 rounded-lg border border-[var(--danger-border)] bg-[var(--danger-soft)] p-3 text-sm text-red-200">{create.error instanceof Error ? create.error.message : "Unable to create project"}</p> : null}
    </Dialog>
  </div>;
}
