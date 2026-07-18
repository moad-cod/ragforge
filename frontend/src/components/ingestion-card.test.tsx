import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {render, screen} from "@testing-library/react";
import {describe, expect, it} from "vitest";
import {IngestionCard} from "@/components/ingestion-card";
import type {Document, IngestionRun} from "@/lib/types";

const failedRun: IngestionRun = {
  ingestion_run_id: "run-1",
  document_id: "document-1",
  document_version_id: "version-1",
  status: "failed",
  airflow_dag_run_id: "dag-1",
  error_message: "No indexable text was found",
  created_at: "2026-07-16T00:00:00Z",
  started_at: "2026-07-16T00:00:01Z",
  finished_at: "2026-07-16T00:00:02Z",
  progress: {
    bronze: true,
    silver: false,
    gold: false,
    qdrant: false,
  },
};

const document: Document = {
  document_id: "document-1",
  project_id: "project-1",
  current_version_id: null,
  filename: "empty.txt",
  source_type: "file",
  mime_type: "text/plain",
  extension: ".txt",
  status: "failed",
  created_by: "user-1",
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

describe("IngestionCard", () => {
  it("renders durable failure details and a safe retry action", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <IngestionCard
          initialRun={failedRun}
          document={document}
          projectId="project-1"
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText("Document processing failed")).toBeInTheDocument();
    expect(screen.getByText("No indexable text was found")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {name: "Retry from Bronze"}),
    ).toBeInTheDocument();
  });
});
