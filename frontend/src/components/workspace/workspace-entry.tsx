"use client";

import {useQuery} from "@tanstack/react-query";
import {AlertTriangle, LoaderCircle} from "lucide-react";
import {apiFetch} from "@/lib/api";
import type {Document} from "@/lib/types";
import {KnowledgeWorkspace} from "@/components/workspace/knowledge-workspace";

export function WorkspaceEntry({projectId}: {projectId: string}) {
  const {isLoading, isError, refetch} = useQuery({
    queryKey: ["documents", projectId],
    queryFn: () => apiFetch<Document[]>(`/documents/?project_id=${projectId}`),
    retry: 1,
  });
  if (isError) return <div className="flex h-full flex-col items-center justify-center text-center"><AlertTriangle className="size-5 text-red-300" /><h1 className="mt-3 text-sm font-semibold">Project state could not be loaded</h1><p className="mt-1 text-[10px] text-[#64736d]">Check the backend connection and try again.</p><button onClick={() => void refetch()} className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-[10px] text-[#a9b7b0]">Try again</button></div>;
  if (isLoading) return <div className="flex h-full items-center justify-center"><div className="flex items-center gap-2 text-[10px] text-[#71847b]"><LoaderCircle className="size-4 animate-spin text-[var(--accent)]" />Preparing your project experience…</div></div>;
  return <KnowledgeWorkspace projectId={projectId} />;
}
