import {PlannedFeaturePage} from "@/components/planned-feature-page";

export default function ExperimentsPage() {
  return <PlannedFeaturePage
    eyebrow="Research"
    title="Experiments"
    description="Cross-project experiment indexes will appear here when the backend exposes experiment records. For now, open a project to prepare sources, playground checks, and pipeline runs."
    primaryHref="/projects"
    primaryLabel="Open projects"
    available={[
      "Project workspaces already support sources, playground queries, pipeline runs, and retrieval trace inspection.",
      "Operational observability is available from real ingestion and query records.",
    ]}
    planned={[
      "Cross-project experiment list with status, orchestrator, dataset, model, and timestamps.",
      "Experiment creation flow with reproducible configuration snapshots.",
      "Export links for benchmark artifacts and reports.",
    ]}
  />;
}
