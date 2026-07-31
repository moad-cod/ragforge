import {AlertTriangle, ArrowRight, CheckCircle2, Clock3, Database, FileStack, FolderKanban, Workflow} from "lucide-react";
import Link from "next/link";
import {PageHeader} from "@/components/page-header";
import {Button} from "@/components/ui/button";

type PlannedFeaturePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  projectId?: string;
  projectName?: string;
  primaryHref?: string;
  primaryLabel?: string;
  available?: string[];
  planned?: string[];
};

export function PlannedFeaturePage({
  eyebrow,
  title,
  description,
  projectId,
  projectName,
  primaryHref,
  primaryLabel = "Open project sources",
  available = [],
  planned = [],
}: PlannedFeaturePageProps) {
  const fallbackHref = projectId ? `/projects/${projectId}/sources` : "/projects";
  const nextHref = primaryHref ?? fallbackHref;
  const contextLinks = projectId
    ? [
        ["Sources", `/projects/${projectId}/sources`, FileStack],
        ["Playground", `/projects/${projectId}/playground`, Database],
        ["Pipelines", `/projects/${projectId}/pipelines`, Workflow],
      ] as const
    : [
        ["Projects", "/projects", FolderKanban],
        ["Runs", "/runs", Workflow],
        ["Observability", "/observability", Database],
      ] as const;

  return <div className="mx-auto max-w-6xl space-y-6">
    <PageHeader
      eyebrow={eyebrow}
      title={title}
      description={description}
      actions={<Link href={nextHref}><Button><ArrowRight className="size-4" />{primaryLabel}</Button></Link>}
    />
    {projectName ? <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-[9px] font-semibold uppercase tracking-[.14em] text-[#817a72]">Project context</p>
      <h2 className="mt-2 text-sm font-semibold">{projectName}</h2>
      <p className="mono mt-1 text-[8px] text-[#5c5751]">{projectId}</p>
    </section> : null}
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="rounded-xl border border-[var(--warning-border)] bg-[var(--warning-soft)] p-5">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface)] text-[var(--warning)]"><AlertTriangle className="size-4" /></span>
          <div>
            <h2 className="text-sm font-semibold text-[var(--accent-strong)]">Backend support is not available yet</h2>
            <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">This screen is wired into the redesigned research workflow, but it only shows real supported capabilities. Experiment configurations, comparison matrices, cost metrics, and quality scores will appear when matching backend endpoints exist.</p>
          </div>
        </div>
      </section>
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
        <div className="flex items-center gap-2">
          <Clock3 className="size-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold">What you can do now</h2>
        </div>
        <div className="mt-4 grid gap-2">
          {contextLinks.map(([label, href, Icon]) => <Link key={label} href={href} className="flex items-center gap-3 rounded-lg border border-white/[0.07] bg-white/[0.018] p-3 text-xs text-[var(--ink-muted)] hover:border-[var(--accent-border)] hover:text-white">
            <Icon className="size-4 text-[var(--accent)]" />
            <span>{label}</span>
            <ArrowRight className="ml-auto size-3" />
          </Link>)}
        </div>
      </section>
    </div>
    <div className="grid gap-4 md:grid-cols-2">
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
        <h2 className="text-sm font-semibold">Available today</h2>
        <ul className="mt-4 space-y-2">
          {available.length ? available.map((item) => <li key={item} className="flex gap-2 text-xs leading-5 text-[var(--ink-muted)]"><CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-[var(--success)]" />{item}</li>) : <li className="text-xs text-[var(--ink-faint)]">Open a project to use current source, pipeline, and playground workflows.</li>}
        </ul>
      </section>
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
        <h2 className="text-sm font-semibold">Planned backend contract</h2>
        <ul className="mt-4 space-y-2">
          {planned.length ? planned.map((item) => <li key={item} className="flex gap-2 text-xs leading-5 text-[var(--ink-muted)]"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--warning)]" />{item}</li>) : <li className="text-xs text-[var(--ink-faint)]">No planned fields have been declared for this surface yet.</li>}
        </ul>
      </section>
    </div>
  </div>;
}
