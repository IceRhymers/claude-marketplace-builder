import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageBubble } from "./MessageBubble";

describe("MessageBubble", () => {
  it("renders user message with correct content", () => {
    render(
      <MessageBubble
        role="user"
        content="Hello, assistant!"
        createdAt="2024-01-01T00:00:00Z"
      />
    );
    expect(screen.getByText("Hello, assistant!")).toBeInTheDocument();
  });

  it("renders assistant message with Markdown", () => {
    render(
      <MessageBubble
        role="assistant"
        content="**Bold text** and _italic_"
        createdAt="2024-01-01T00:00:00Z"
      />
    );
    // Markdown should render as HTML elements
    expect(screen.getByRole("strong") ?? screen.getByText(/Bold text/)).toBeInTheDocument();
  });

  it("user messages have a distinct role indicator", () => {
    const { container } = render(
      <MessageBubble
        role="user"
        content="User message"
        createdAt="2024-01-01T00:00:00Z"
      />
    );
    expect(container.querySelector("[data-role='user']")).toBeInTheDocument();
  });

  it("assistant messages have a distinct role indicator", () => {
    const { container } = render(
      <MessageBubble
        role="assistant"
        content="Assistant message"
        createdAt="2024-01-01T00:00:00Z"
      />
    );
    expect(container.querySelector("[data-role='assistant']")).toBeInTheDocument();
  });
});
