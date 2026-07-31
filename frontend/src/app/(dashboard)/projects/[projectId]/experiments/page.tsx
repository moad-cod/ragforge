import {ProjectPlannedFeaturePage} from "@/components/project-planned-feature-page";

export default async function ProjectExperimentsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ProjectPlannedFeaturePage
    projectId={projectId}
    eyebrow="Research"
    title="Experiments"
    description="Experiment runs will compare orchestrators, datasets, retrieval settings, latency, reliability, and cost from one project-scoped research surface."
    primaryHref={`/projects/${projectId}/sources`}
    primaryLabel="Prepare sources"
    available={[
      "Use project sources as the corpus for future experiments.",
      "Use the playground to test retrieval settings and inspect evidence.",
      "Use pipelines to verify that sources are indexed before benchmarking.",
    ]}
    planned={[
      "Experiment configuration snapshots with orchestrator, model, chunker, concurrency, and dataset.",
      "Run lifecycle, logs, resource metrics, and exported artifacts.",
      "Quality, latency, reliability, and cost summaries once backend evaluation endpoints exist.",
    ]}
  />;
}
