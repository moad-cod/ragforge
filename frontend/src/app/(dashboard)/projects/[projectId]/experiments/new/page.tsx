import {ProjectPlannedFeaturePage} from "@/components/project-planned-feature-page";

export default async function NewExperimentPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ProjectPlannedFeaturePage
    projectId={projectId}
    eyebrow="Experiment builder"
    title="New experiment"
    description="The guided experiment builder is reserved for backend-supported benchmark configurations. Current UI links you to the sources, playground, and pipelines needed before that contract lands."
    primaryHref={`/projects/${projectId}/pipelines`}
    primaryLabel="Review pipelines"
    available={[
      "Upload sources and evaluation documents.",
      "Run playground queries against indexed sources.",
      "Inspect ingestion runs before executing comparable benchmarks.",
    ]}
    planned={[
      "Dataset selector and workload manifest.",
      "Airflow versus Celery orchestrator selection.",
      "RAG configuration snapshot and validation gates.",
      "Submission to benchmark worker when backend support exists.",
    ]}
  />;
}
