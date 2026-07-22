import {IngestionRunDetail} from "@/components/ingestion-run-detail";
export default async function RunDetailPage({params}: {params: Promise<{projectId: string; runId: string}>}) {const {projectId, runId} = await params; return <IngestionRunDetail projectId={projectId} runId={runId} />;}
