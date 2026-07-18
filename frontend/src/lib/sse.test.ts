import {describe, expect, it, vi} from "vitest";
import {consumeSSE} from "@/lib/sse";

function streamedResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: {"Content-Type": "text/event-stream"},
    },
  );
}

describe("consumeSSE", () => {
  it("parses fragmented events and ignores heartbeats", async () => {
    const onEvent = vi.fn();
    const onId = vi.fn();
    const response = streamedResponse([
      ": heartbeat\n\nid: op-1:1\nevent: query.rece",
      'ived\ndata: {"event":"query.received","sequence":1}\n\n',
      'event: query.token\ndata: {"event":"query.token","text":"Hello"}\n\n',
    ]);

    await consumeSSE(response, {onEvent, onId});

    expect(onId).toHaveBeenCalledWith("op-1:1");
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls[1][0]).toMatchObject({
      event: "query.token",
      text: "Hello",
    });
  });

  it("surfaces API errors before reading a stream", async () => {
    const response = Response.json({detail: "Project not found"}, {status: 404});

    await expect(
      consumeSSE(response, {onEvent: vi.fn()}),
    ).rejects.toThrow("Project not found");
  });
});
