import {ObservabilityDashboard} from "@/components/observability-dashboard";
export default async function ProjectObservabilityPage({params}: {params: Promise<{projectId: string}>}) {const {projectId} = await params; return <ObservabilityDashboard projectId={projectId} />;}
