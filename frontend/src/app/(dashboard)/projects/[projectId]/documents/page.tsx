import {WorkspaceEntry} from "@/components/workspace/workspace-entry";

export default async function DocumentsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <WorkspaceEntry projectId={projectId} />;
}
