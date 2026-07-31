import {ProjectPipelinesPage} from "@/components/project-pipelines-page";

export default async function PipelinesPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ProjectPipelinesPage projectId={projectId} />;
}
