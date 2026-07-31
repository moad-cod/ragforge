import {redirect} from "next/navigation";

export default async function DocumentsPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  redirect(`/projects/${projectId}/sources`);
}
