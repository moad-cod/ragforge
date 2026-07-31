import {ProjectPlannedFeaturePage} from "@/components/project-planned-feature-page";

export default async function ExperimentDetailPage({
  params,
}: {
  params: Promise<{projectId: string; experimentId: string}>;
}) {
  const {projectId, experimentId} = await params;
  return <ProjectPlannedFeaturePage
    projectId={projectId}
    eyebrow="Experiment detail"
    title={`Experiment ${experimentId}`}
    description="Experiment detail pages will display configuration snapshots, progress, metrics, logs, and artifacts once durable experiment records are exposed by the backend."
    primaryHref={`/projects/${projectId}/experiments`}
    primaryLabel="Back to experiments"
    available={[
      "Project sources and pipeline runs remain available while experiment records are planned.",
      "Query details already expose retrieval evidence for manual inspection.",
    ]}
    planned={[
      "Configuration snapshot and reproducibility metadata.",
      "Run status, logs, and output artifacts.",
      "Evaluation metrics and comparison eligibility.",
    ]}
  />;
}
