import {ProjectOnboarding} from "@/components/onboarding/project-onboarding";

export default async function ProjectOnboardingPage({params}: {params: Promise<{projectId: string}>}) {
  const {projectId} = await params;
  return <ProjectOnboarding projectId={projectId} />;
}
