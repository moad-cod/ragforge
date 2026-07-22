import {QueryDetail} from "@/components/query-detail";
export default async function QueryPage({params}: {params: Promise<{projectId: string; queryId: string}>}) {const {projectId, queryId} = await params; return <QueryDetail projectId={projectId} queryId={queryId} />;}
