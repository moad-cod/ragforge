"use client";

import {useQuery} from "@tanstack/react-query";
import {PlannedFeaturePage} from "@/components/planned-feature-page";
import {LoadingState} from "@/components/ui/loading-state";
import {apiFetch} from "@/lib/api";
import type {Project} from "@/lib/types";

type ProjectPlannedFeaturePageProps = {
  projectId: string;
  eyebrow: string;
  title: string;
  description: string;
  primaryHref?: string;
  primaryLabel?: string;
  available?: string[];
  planned?: string[];
};

export function ProjectPlannedFeaturePage(props: ProjectPlannedFeaturePageProps) {
  const project = useQuery({queryKey: ["project", props.projectId], queryFn: () => apiFetch<Project>(`/projects/${props.projectId}`)});
  if (project.isLoading) return <LoadingState label="Loading project context" rows={4} />;

  return <PlannedFeaturePage
    {...props}
    projectName={project.data?.name ?? "Project"}
  />;
}
