import {HistoryWorkspace} from "@/components/history-workspace";

export default async function HistoryPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <HistoryWorkspace projectId={projectId} />;
}
