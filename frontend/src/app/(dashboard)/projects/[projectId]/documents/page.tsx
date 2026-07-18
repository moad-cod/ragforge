import {DocumentsWorkspace} from "@/components/documents-workspace";

export default async function DocumentsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <DocumentsWorkspace projectId={projectId} />;
}
