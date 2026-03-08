import { http, HttpResponse } from "msw";

const CONVERSATION_ID = "test-conv-123";

export const handlers = [
  // GET /api/me
  http.get("/api/me", () => {
    return HttpResponse.json({
      user_id: "test@example.com",
      display_name: "Test User",
    });
  }),

  // GET /api/conversations
  http.get("/api/conversations", () => {
    return HttpResponse.json([
      {
        conversation_id: CONVERSATION_ID,
        title: "Test Conversation",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ]);
  }),

  // POST /api/conversations
  http.post("/api/conversations", () => {
    return HttpResponse.json(
      {
        conversation_id: "new-conv-456",
        created_at: "2024-01-01T00:00:00Z",
      },
      { status: 201 }
    );
  }),

  // GET /api/conversations/:id/messages
  http.get("/api/conversations/:id/messages", () => {
    return HttpResponse.json([
      {
        id: "msg-1",
        role: "user",
        content: "Hello",
        created_at: "2024-01-01T00:00:00Z",
      },
      {
        id: "msg-2",
        role: "assistant",
        content: "Hi there!",
        created_at: "2024-01-01T00:00:01Z",
      },
    ]);
  }),

  // DELETE /api/conversations/:id
  http.delete("/api/conversations/:id", () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // GET /api/conversations/:id/stream (SSE mock)
  http.get("/api/conversations/:id/stream", () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"text_delta","text":"Hello"}\n\n')
        );
        controller.enqueue(
          encoder.encode('data: {"type":"done"}\n\n')
        );
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
      },
    });
  }),

  // GET /api/skills
  http.get("/api/skills", () => {
    return HttpResponse.json([]);
  }),

  // GET /api/mcp
  http.get("/api/mcp", () => {
    return HttpResponse.json({ mcpServers: {} });
  }),

  // GET /health
  http.get("/health", () => {
    return HttpResponse.json({ status: "ok" });
  }),
];
