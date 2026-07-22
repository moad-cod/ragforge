"use client";

import {IngestionPipeline} from "@/components/ingestion-pipeline";
import {useIngestionStream} from "@/hooks/use-ingestion-stream";
import type {Document, IngestionRun} from "@/lib/types";

export function IngestionCard({initialRun, document, projectId}: {initialRun: IngestionRun; document?: Document; projectId: string}) {
  const {run} = useIngestionStream(initialRun);
  return <IngestionPipeline run={run} document={document} projectId={projectId} />;
}
