import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// We test the ConversationPage component in isolation, bypassing the router.
import { ConversationPage } from "./$conversationId";

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderConversation(conversationId: string) {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ConversationPage conversationId={conversationId} />
    </QueryClientProvider>
  );
}

describe("ConversationPage", () => {
  it("renders message history from mock API", async () => {
    renderConversation("test-conv-123");

    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
      expect(screen.getByText("Hi there!")).toBeInTheDocument();
    });
  });

  it("renders the ChatInput component", async () => {
    renderConversation("test-conv-123");

    await waitFor(() => {
      expect(screen.getByRole("textbox")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    });
  });

  it("streaming tokens append to UI as text_delta events arrive", async () => {
    // Use a slow stream that we can observe mid-stream
    let streamController: ReadableStreamDefaultController<Uint8Array>;
    const encoder = new TextEncoder();

    server.use(
      http.get("/api/conversations/:id/stream", () => {
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            streamController = controller;
          },
        });
        return new HttpResponse(stream, {
          headers: { "Content-Type": "text/event-stream" },
        });
      })
    );

    renderConversation("test-conv-123");

    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "test message");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    // Push a text_delta event
    await act(async () => {
      streamController.enqueue(
        encoder.encode('data: {"type":"text_delta","text":"Streaming"}\n\n')
      );
    });

    await waitFor(() => {
      // The streaming message bubble shows "Streaming▊" (with cursor)
      expect(screen.getByText(/Streaming/)).toBeInTheDocument();
    });

    // Close the stream with done
    await act(async () => {
      streamController.enqueue(encoder.encode('data: {"type":"done"}\n\n'));
      streamController.close();
    });
  });

  it("done event stops the stream and re-enables the send button", async () => {
    server.use(
      http.get("/api/conversations/:id/stream", () => {
        const encoder = new TextEncoder();
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode('data: {"type":"text_delta","text":"Done response"}\n\n')
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

    renderConversation("test-conv-123");

    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "send this");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    // After done event, the send button should be re-enabled (input has focus, but empty)
    // The streaming completes, isStreaming returns to false
    await waitFor(() => {
      // textarea is no longer disabled
      expect(screen.getByRole("textbox")).not.toBeDisabled();
    }, { timeout: 8000 });
  });

  it("shows empty state when conversation has no messages", async () => {
    server.use(
      http.get("/api/conversations/:id/messages", () => {
        return HttpResponse.json([]);
      })
    );

    renderConversation("new-conv-456");

    await waitFor(() => {
      expect(screen.getByText(/send a message/i)).toBeInTheDocument();
    });
  });
});
