import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("renders textarea and send button", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("send button is disabled during active stream", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={true} />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("textarea clears after send", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} />);

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "Hello world");
    expect(textarea).toHaveValue("Hello world");

    const sendBtn = screen.getByRole("button", { name: /send/i });
    await userEvent.click(sendBtn);

    expect(textarea).toHaveValue("");
  });

  it("onSend called with message text", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} isStreaming={false} />);

    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "Hello world");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("Hello world");
  });

  it("send button disabled when textarea is empty", () => {
    render(<ChatInput onSend={vi.fn()} isStreaming={false} />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
