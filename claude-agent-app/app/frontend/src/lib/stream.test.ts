import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { streamMessage } from "./stream";

describe("stream.ts", () => {
  describe("streamMessage", () => {
    it("calls onEvent with text_delta events", async () => {
      const events: Array<{ type: string; text?: string }> = [];
      await streamMessage("test-conv-123", "Hello", (event) => {
        events.push(event);
      });
      const textDeltas = events.filter((e) => e.type === "text_delta");
      expect(textDeltas.length).toBeGreaterThan(0);
      expect(textDeltas[0].text).toBe("Hello");
    });

    it("calls onEvent with done event", async () => {
      const events: Array<{ type: string }> = [];
      await streamMessage("test-conv-123", "Hello", (event) => {
        events.push(event);
      });
      const doneEvents = events.filter((e) => e.type === "done");
      expect(doneEvents.length).toBe(1);
    });

    it("handles tool_use and tool_result events", async () => {
      server.use(
        http.get("/api/conversations/:id/stream", () => {
          const encoder = new TextEncoder();
          const stream = new ReadableStream({
            start(controller) {
              controller.enqueue(
                encoder.encode(
                  'data: {"type":"tool_use","tool":"search","input":{"query":"test"}}\n\n'
                )
              );
              controller.enqueue(
                encoder.encode(
                  'data: {"type":"tool_result","tool":"search","output":"results"}\n\n'
                )
              );
              controller.enqueue(
                encoder.encode('data: {"type":"done"}\n\n')
              );
              controller.close();
            },
          });
          return new HttpResponse(stream, {
            headers: { "Content-Type": "text/event-stream" },
          });
        })
      );

      const events: Array<{ type: string }> = [];
      await streamMessage("test-conv-123", "search", (event) => {
        events.push(event);
      });

      const types = events.map((e) => e.type);
      expect(types).toContain("tool_use");
      expect(types).toContain("tool_result");
      expect(types).toContain("done");
    });

    it("handles error events without throwing", async () => {
      server.use(
        http.get("/api/conversations/:id/stream", () => {
          const encoder = new TextEncoder();
          const stream = new ReadableStream({
            start(controller) {
              controller.enqueue(
                encoder.encode('data: {"type":"error","detail":"test error"}\n\n')
              );
              controller.close();
            },
          });
          return new HttpResponse(stream, {
            headers: { "Content-Type": "text/event-stream" },
          });
        })
      );

      const events: Array<{ type: string }> = [];
      await streamMessage("test-conv-123", "test", (event) => {
        events.push(event);
      });

      expect(events.some((e) => e.type === "error")).toBe(true);
    });
  });
});
