import {PlannedFeaturePage} from "@/components/planned-feature-page";

export default function ComparisonsPage() {
  return <PlannedFeaturePage
    eyebrow="Research"
    title="Comparisons"
    description="Comparison workspaces will compare compatible benchmark runs across Airflow, Celery, datasets, retrieval settings, quality, latency, reliability, resources, and cost."
    primaryHref="/projects"
    primaryLabel="Prepare projects"
    available={[
      "Use project pipelines and observability to inspect current operational records.",
      "Use query detail pages to inspect retrieval evidence and answer outcomes.",
    ]}
    planned={[
      "Compatibility checks for comparable experiment configurations.",
      "Side-by-side metrics and configuration diffs.",
      "Exportable comparison report when backend result artifacts are available.",
    ]}
  />;
}
