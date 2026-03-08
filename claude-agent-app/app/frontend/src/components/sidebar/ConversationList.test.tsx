import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConversationList } from "./ConversationList";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("ConversationList", () => {
  it("renders conversation titles from mock API", async () => {
    renderWithProviders(
      <ConversationList
        activeConversationId={null}
        onSelectConversation={vi.fn()}
        onNewConversation={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Test Conversation")).toBeInTheDocument();
    });
  });

  it("highlights the active conversation", async () => {
    renderWithProviders(
      <ConversationList
        activeConversationId="test-conv-123"
        onSelectConversation={vi.fn()}
        onNewConversation={vi.fn()}
      />
    );

    await waitFor(() => {
      const item = screen.getByText("Test Conversation").closest("button");
      expect(item).toHaveAttribute("aria-selected", "true");
    });
  });

  it("clicking New Chat calls onNewConversation callback", async () => {
    const onNew = vi.fn();
    renderWithProviders(
      <ConversationList
        activeConversationId={null}
        onSelectConversation={vi.fn()}
        onNewConversation={onNew}
      />
    );

    const newChatBtn = await waitFor(() => screen.getByText("New Chat"));
    await userEvent.click(newChatBtn);
    expect(onNew).toHaveBeenCalledOnce();
  });

  it("shows empty state when no conversations", async () => {
    server.use(
      http.get("/api/conversations", () => {
        return HttpResponse.json([]);
      })
    );

    renderWithProviders(
      <ConversationList
        activeConversationId={null}
        onSelectConversation={vi.fn()}
        onNewConversation={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText("Test Conversation")).not.toBeInTheDocument();
    });
  });
});
