import {QueryHistoryPage} from "@/components/query-history-page";
export default async function HistoryPage({params}: {params: Promise<{projectId: string}>}) {const {projectId} = await params; return <QueryHistoryPage projectId={projectId} />;}
