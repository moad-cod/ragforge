import {ProjectOverview} from "@/components/project-overview";

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ProjectOverview projectId={projectId} />;
}
