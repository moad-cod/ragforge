import {ProjectPlannedFeaturePage} from "@/components/project-planned-feature-page";

export default async function ProjectEvaluationPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ProjectPlannedFeaturePage
    projectId={projectId}
    eyebrow="Evaluation"
    title="Evaluation"
    description="Evaluation will collect real quality, latency, reliability, resource, and cost metrics for project experiments. Until backend metrics exist, the UI keeps this surface explicit and empty."
    primaryHref={`/projects/${projectId}/playground`}
    primaryLabel="Open playground"
    available={[
      "Playground query traces include retrieved chunks, scores, and answer status.",
      "Observability shows real query latency and cache behavior from persisted records.",
      "Pipeline runs show real ingestion status and retry state.",
    ]}
    planned={[
      "Metric drill-down by experiment, dataset, model, and orchestrator.",
      "Failure-rate, throughput, cost, and resource summaries.",
      "Report export tied to reproducible experiment snapshots.",
    ]}
  />;
}
