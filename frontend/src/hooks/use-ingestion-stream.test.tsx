import {renderHook, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {useIngestionStream} from "@/hooks/use-ingestion-stream";
import {apiFetch} from "@/lib/api";
import type {IngestionRun} from "@/lib/types";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

const initialRun: IngestionRun = {
  ingestion_run_id: "run-1",
  document_id: "document-1",
  document_version_id: "version-1",
  status: "running",
  airflow_dag_run_id: "dag-1",
  error_message: null,
  created_at: "2026-07-16T00:00:00Z",
  started_at: "2026-07-16T00:00:01Z",
  finished_at: null,
  progress: {
    bronze: true,
    silver: false,
    gold: false,
    qdrant: false,
  },
  embedding_progress: null,
};

function terminalStream() {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'id: 1-0\nevent: ingestion.completed\ndata: {"event":"ingestion.completed","status":"indexed","progress":{"bronze":true,"silver":true,"gold":true,"qdrant":true}}\n\n',
          ),
        );
        controller.close();
      },
    }),
    {status: 200, headers: {"Content-Type": "text/event-stream"}},
  );
}

describe("useIngestionStream", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("applies a terminal stream event", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(terminalStream());

    const {result} = renderHook(() => useIngestionStream(initialRun));

    await waitFor(() => expect(result.current.run.status).toBe("indexed"));
    expect(result.current.run.progress.qdrant).toBe(true);
    expect(localStorage.getItem("ragforge:ingestion:run-1:last-event-id")).toBe(
      "1-0",
    );
  });

  it("recovers through the durable status endpoint before reconnecting", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("stream offline"))
      .mockResolvedValueOnce(terminalStream());
    vi.mocked(apiFetch).mockResolvedValue({...initialRun, status: "running"});

    const {result} = renderHook(() => useIngestionStream(initialRun));

    await waitFor(() => expect(result.current.run.status).toBe("indexed"), {
      timeout: 4000,
    });
    expect(apiFetch).toHaveBeenCalledWith("/ingest/runs/run-1");
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
