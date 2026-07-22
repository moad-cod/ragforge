import {IngestionRunsPage} from "@/components/ingestion-runs-page";
export default async function ProjectRunsPage({params}: {params: Promise<{projectId: string}>}) {const {projectId} = await params; return <IngestionRunsPage projectId={projectId} />;}
