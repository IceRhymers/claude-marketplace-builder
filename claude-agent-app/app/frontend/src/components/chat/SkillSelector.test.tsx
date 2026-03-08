import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SkillSelector } from "./SkillSelector";

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = makeQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("SkillSelector", () => {
  it("renders nothing when skills list is empty", async () => {
    const { container } = renderWithProviders(
      <SkillSelector value={null} onChange={vi.fn()} />
    );
    // The default MSW handler returns [] for /api/skills
    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("renders skill options when skills are available", async () => {
    server.use(
      http.get("/api/skills", () => {
        return HttpResponse.json([
          { name: "slack-assistant", description: "Slack helper" },
          { name: "code-review", description: "Code review skill" },
        ]);
      })
    );

    renderWithProviders(<SkillSelector value={null} onChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /select skill/i })).toBeInTheDocument();
      expect(screen.getByText("slack-assistant")).toBeInTheDocument();
      expect(screen.getByText("code-review")).toBeInTheDocument();
    });
  });

  it("calls onChange when a skill is selected", async () => {
    server.use(
      http.get("/api/skills", () => {
        return HttpResponse.json([
          { name: "slack-assistant" },
        ]);
      })
    );

    const onChange = vi.fn();
    renderWithProviders(<SkillSelector value={null} onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /select skill/i })).toBeInTheDocument();
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /select skill/i }),
      "slack-assistant"
    );

    expect(onChange).toHaveBeenCalledWith("slack-assistant");
  });

  it("shows selected skill as current value", async () => {
    server.use(
      http.get("/api/skills", () => {
        return HttpResponse.json([
          { name: "slack-assistant" },
          { name: "code-review" },
        ]);
      })
    );

    renderWithProviders(
      <SkillSelector value="slack-assistant" onChange={vi.fn()} />
    );

    await waitFor(() => {
      const select = screen.getByRole("combobox", { name: /select skill/i }) as HTMLSelectElement;
      expect(select.value).toBe("slack-assistant");
    });
  });
});
