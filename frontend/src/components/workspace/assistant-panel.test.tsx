import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, describe, expect, it, vi} from "vitest";
import {AssistantPanel} from "@/components/workspace/assistant-panel";
import {apiFetch} from "@/lib/api";
import type {QueryTrace} from "@/lib/types";
import type {WorkspaceDocument} from "@/components/workspace/workspace-data";

vi.mock("@/lib/api", () => ({apiFetch: vi.fn()}));

const document: WorkspaceDocument = {
  document_id: "document-1", project_id: "project-1", current_version_id: "version-1", filename: "Report.pdf", source_type: "file", mime_type: "application/pdf", extension: ".pdf", status: "indexed", created_by: "user-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", size: "", pages: 0, chunks: 0, version: 1, owner: "",
};

const trace: QueryTrace = {
  query_log_id: "query-1", project_id: "project-1", question: "What changed?", answer: "Hello", provider: "gemini", model: "gemini-2.5-flash", latency_ms: 20, cache_hit: false, route: "rag", created_at: "2026-01-01T00:00:00Z",
  retrievals: [{retrieval_log_id: "retrieval-1", chunk_id: "chunk-1", document_id: "document-1", document_name: "Report.pdf", document_version_id: "version-1", chunk_index: 2, text: "Supporting evidence", section_title: "Changes", page_start: 2, page_end: 2, qdrant_score: .8, rerank_score: .9, rank: 1, retrieval_strategy: "hybrid", used_in_answer: true}],
};

function stream() {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({start(controller) {controller.enqueue(encoder.encode('event: query.token\ndata: {"event":"query.token","text":"Hello"}\n\nevent: query.completed\ndata: {"event":"query.completed","query_log_id":"query-1"}\n\n')); controller.close();}}), {status: 200, headers: {"Content-Type": "text/event-stream"}});
}

describe("AssistantPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("streams an answer with a supported document filter and opens its citation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(stream());
    vi.mocked(apiFetch).mockResolvedValue(trace);
    const onCitation = vi.fn();
    render(<QueryClientProvider client={new QueryClient()}><AssistantPanel projectId="project-1" projectName="Research" documents={[document]} selectedIds={["document-1"]} onRemoveSelected={vi.fn()} onCitation={onCitation} onOpenTrace={vi.fn()} /></QueryClientProvider>);

    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/Ask a question about your knowledge base/), "What changed?");
    await user.click(screen.getByRole("button", {name: "Send question"}));

    expect(await screen.findByText("Execution trace")).toBeInTheDocument();
    expect(screen.getByText("Generated response")).toBeInTheDocument();
    expect(await screen.findByText("Hello")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", {name: /Report · p\.2/})).toBeInTheDocument());
    const [, request] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(String(request?.body))).toMatchObject({project_id: "project-1", document_id: "document-1", question: "What changed?"});
    expect(JSON.parse(String(request?.body))).not.toHaveProperty("document_ids");

    await user.click(screen.getByRole("button", {name: /Report · p\.2/}));
    expect(onCitation).toHaveBeenCalledWith(trace.retrievals[0]);
  });
});
