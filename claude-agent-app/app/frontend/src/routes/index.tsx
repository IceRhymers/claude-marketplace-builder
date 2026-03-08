import { createFileRoute } from "@tanstack/react-router";
import { Bot } from "lucide-react";

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <Bot className="h-16 w-16 text-muted-foreground" />
      <h1 className="text-2xl font-semibold">Claude Agent App</h1>
      <p className="text-muted-foreground max-w-sm">
        Select an existing conversation from the sidebar or create a new chat to
        get started.
      </p>
    </div>
  );
}
