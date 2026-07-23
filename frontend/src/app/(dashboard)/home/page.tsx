"use client";

import {Database, FolderKanban, History, Workflow} from "lucide-react";
import Link from "next/link";
import {MetricCard} from "@/components/metric-card";
import {PageHeader} from "@/components/page-header";
import {StatusBadge} from "@/components/status-badge";
import {ErrorState} from "@/components/ui/error-state";
import {LoadingState} from "@/components/ui/loading-state";
import {useWorkspaceOverview} from "@/hooks/use-workspace-overview";
import {relativeTime} from "@/lib/utils";

export default function HomePage() {
  const overview = useWorkspaceOverview({documents: true, runs: true, history: true});
  if (overview.pending) return <LoadingState label="Loading home dashboard" rows={6} />;
  if (overview.error) return <ErrorState title="Workspace summary could not be loaded" description="One or more control-plane endpoints returned an error." onRetry={() => void overview.refetch()} />;
  const indexed = overview.documents.filter((document) => document.status === "indexed").length;
  const active = overview.runs.filter((run) => !["indexed","failed","cancelled"].includes(run.status)).length;
  return <div className="mx-auto max-w-7xl space-y-6"><PageHeader eyebrow="Workspace" title="Home" description="A live summary derived from your owned projects, durable documents, ingestion runs, and query logs." />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Projects" value={overview.projects.length} detail="Owned knowledge workspaces" icon={FolderKanban} /><MetricCard label="Indexed documents" value={`${indexed}/${overview.documents.length}`} detail="Ready for retrieval" icon={Database} /><MetricCard label="Active ingestion" value={active} detail="Non-terminal pipeline runs" icon={Workflow} /><MetricCard label="Queries" value={overview.history.length} detail="Loaded durable history" icon={History} /></div>
    <section className="rounded-xl border border-white/[0.08] bg-[var(--surface)]"><div className="flex items-center justify-between border-b border-white/[0.08] p-4"><div><h2 className="text-sm font-semibold">Recent projects</h2><p className="mt-1 text-[9px] text-[#64736d]">Continue where you left off</p></div><Link href="/projects" className="text-[10px] text-[var(--accent)]">View all →</Link></div>{overview.projects.length ? <div className="divide-y divide-white/[0.07]">{overview.projects.slice(0,6).map((project) => <Link key={project.project_id} href={`/projects/${project.project_id}/documents`} className="flex items-center gap-3 p-4 hover:bg-white/[0.02]"><span className="flex size-9 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]"><FolderKanban className="size-4" /></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium">{project.name}</span><span className="mt-1 block text-[8px] text-[#53625b]">Updated {relativeTime(project.updated_at)}</span></span><StatusBadge status="ready" /></Link>)}</div> : <p className="p-8 text-center text-[10px] text-[#64736d]">Create a project to begin building a knowledge base.</p>}</section>
  </div>;
}
