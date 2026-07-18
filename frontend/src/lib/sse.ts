import type {StreamEvent} from "@/lib/types";

type SSEHandlers = {
  onEvent: (event: StreamEvent) => void;
  onId?: (id: string) => void;
};

export async function consumeSSE(
  response: Response,
  handlers: SSEHandlers,
): Promise<void> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : `Stream failed with status ${response.status}`;
    throw new Error(message);
  }
  if (!response.body) throw new Error("Streaming response has no body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const processBlock = (block: string) => {
    let eventName = "message";
    let eventId = "";
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (!line || line.startsWith(":")) continue;
      const separator = line.indexOf(":");
      const field = separator === -1 ? line : line.slice(0, separator);
      const value =
        separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
      if (field === "event") eventName = value;
      if (field === "id") eventId = value;
      if (field === "data") data.push(value);
    }
    if (!data.length) return;
    const payload = JSON.parse(data.join("\n")) as StreamEvent;
    payload.event = String(payload.event || eventName);
    if (eventId) {
      payload.id = eventId;
      handlers.onId?.(eventId);
    }
    handlers.onEvent(payload);
  };

  while (true) {
    const {done, value} = await reader.read();
    buffer += decoder.decode(value, {stream: !done});
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    blocks.forEach(processBlock);
    if (done) break;
  }
  if (buffer.trim()) processBlock(buffer);
}
