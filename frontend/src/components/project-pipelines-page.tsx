"use client";

import {useQuery} from "@tanstack/react-query";
import {Database, FileStack, Settings2, Workflow} from "lucide-react";
import Link from "next/link";
import {IngestionRunsPage} from "@/components/ingestion-runs-page";
import {PageHeader} from "@/components/page-header";
import {StatusBadge} from "@/components/status-badge";
import {Button} from "@/components/ui/button";
import {apiFetch} from "@/lib/api";
import type {Chunker, Project} from "@/lib/types";

export function ProjectPipelinesPage({projectId}: {projectId: string}) {
  const project = useQuery({queryKey: ["project", projectId], queryFn: () => apiFetch<Project>(`/projects/${projectId}`)});
  const chunkers = useQuery({queryKey: ["chunkers"], queryFn: () => apiFetch<Chunker[]>("/chunkers")});
  const recommended = chunkers.data?.find((chunker) => chunker.default) ?? chunkers.data?.find((chunker) => chunker.id === "paragraph");

  return <div className="space-y-8">
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        eyebrow={project.data?.name ?? "Project pipelines"}
        title="Pipelines"
        description="Configure source ingestion defaults, review backend-supported processing behavior, and inspect project runs without mixing them into global monitoring."
        actions={<Link href={`/projects/${projectId}/sources`}><Button><FileStack className="size-4" />Add sources</Button></Link>}
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="flex items-center gap-2"><Workflow className="size-4 text-[var(--accent)]" /><h2 className="text-sm font-semibold">Execution model</h2></div>
          <p className="mt-3 text-xs leading-5 text-[var(--ink-muted)]">File sources run through the durable backend ingestion pipeline. The frontend follows status through run records and SSE recovery.</p>
          <div className="mt-4"><StatusBadge status="available" /></div>
        </section>
        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="flex items-center gap-2"><Settings2 className="size-4 text-[var(--accent)]" /><h2 className="text-sm font-semibold">Chunking default</h2></div>
          <p className="mt-3 text-xs leading-5 text-[var(--ink-muted)]">{recommended ? `${recommended.name}: ${recommended.short_description}` : "Chunker catalog is loading or unavailable."}</p>
          <p className="mt-3 text-[9px] leading-4 text-[#77716a]">Project-level pipeline configuration is not persisted by the current backend; selected chunkers are stored on document versions.</p>
        </section>
        <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="flex items-center gap-2"><Database className="size-4 text-[var(--accent)]" /><h2 className="text-sm font-semibold">Artifacts</h2></div>
          <p className="mt-3 text-xs leading-5 text-[var(--ink-muted)]">The run detail view exposes Bronze, Silver, Gold, and Qdrant completion state as reported by the backend.</p>
          <Link href={`/projects/${projectId}/sources`} className="mt-4 inline-flex text-[10px] text-[var(--accent)] hover:text-[var(--accent-hover)]">Open source manager</Link>
        </section>
      </div>
    </div>
    <IngestionRunsPage projectId={projectId} />
  </div>;
}
