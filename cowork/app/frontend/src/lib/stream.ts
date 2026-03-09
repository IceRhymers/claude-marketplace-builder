/**
 * SSE streaming client for the cowork chat endpoint.
 */

export type StreamEvent =
  | { type: "text_delta"; text: string }
  | { type: "tool_use"; tool: string; input: unknown }
  | { type: "tool_result"; tool: string; output: string }
  | { type: "done"; message_id?: string }
  | { type: "error"; detail: string };

export type StreamEventCallback = (event: StreamEvent) => void;

/**
 * Stream a message to the agent and call onEvent for each SSE event.
 *
 * Uses fetch + ReadableStream to consume the SSE endpoint.
 * Resolves when the stream closes (done or error event received).
 */
export async function streamMessage(
  conversationId: string,
  message: string,
  onEvent: StreamEventCallback
): Promise<void> {
  const url = `/api/conversations/${conversationId}/stream?message=${encodeURIComponent(message)}`;

  const resp = await fetch(url);
  if (!resp.ok) {
    onEvent({ type: "error", detail: `HTTP ${resp.status}` });
    return;
  }

  if (!resp.body) {
    onEvent({ type: "error", detail: "No response body" });
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split on SSE event boundaries (\n\n)
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const lines = part.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data) as StreamEvent;
              onEvent(event);
              if (event.type === "done" || event.type === "error") {
                return;
              }
            } catch {
              // Ignore parse errors for malformed lines
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
