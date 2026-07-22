"use client";

import {useQueries, useQuery} from "@tanstack/react-query";
import {apiFetch} from "@/lib/api";
import type {Document, IngestionRun, Project, QueryHistoryItem} from "@/lib/types";

export function useWorkspaceOverview(options: {documents?: boolean; runs?: boolean; history?: boolean} = {}) {
  const projectsQuery = useQuery({queryKey: ["projects"], queryFn: () => apiFetch<Project[]>("/projects/")});
  const projects = projectsQuery.data ?? [];
  const documentQueries = useQueries({queries: options.documents === false ? [] : projects.map((project) => ({queryKey: ["documents", project.project_id], queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${project.project_id}`)}))});
  const runQueries = useQueries({queries: options.runs ? projects.map((project) => ({queryKey: ["ingestion-runs", project.project_id], queryFn: () => apiFetch<IngestionRun[]>(`/ingest/runs?project_id=${project.project_id}&limit=100`)})) : []});
  const historyQueries = useQueries({queries: options.history ? projects.map((project) => ({queryKey: ["query-history", project.project_id], queryFn: () => apiFetch<QueryHistoryItem[]>(`/rag/projects/${project.project_id}/history?limit=100`)})) : []});
  const projectMap = new Map(projects.map((project) => [project.project_id, project]));
  const documents = documentQueries.flatMap((query, index) => (query.data ?? []).map((document) => ({...document, project: projects[index]})));
  const runs = runQueries.flatMap((query, index) => (query.data ?? []).map((run) => ({...run, project: projects[index]})));
  const history = historyQueries.flatMap((query, index) => (query.data ?? []).map((item) => ({...item, project: projects[index]})));
  const pending = projectsQuery.isLoading || documentQueries.some((query) => query.isLoading) || runQueries.some((query) => query.isLoading) || historyQueries.some((query) => query.isLoading);
  const error = projectsQuery.isError || documentQueries.some((query) => query.isError) || runQueries.some((query) => query.isError) || historyQueries.some((query) => query.isError);
  return {projects, projectMap, documents, runs, history, pending, error, refetch: async () => {await projectsQuery.refetch(); await Promise.all([...documentQueries, ...runQueries, ...historyQueries].map((query) => query.refetch()));}};
}
