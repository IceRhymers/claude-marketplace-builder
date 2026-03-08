import { createRootRouteWithContext, Outlet, useNavigate } from "@tanstack/react-router";
import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Bot, User } from "lucide-react";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ConversationList } from "@/components/sidebar/ConversationList";
import { createConversation } from "@/lib/api";

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});

function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutInner />
    </AuthProvider>
  );
}

function RootLayoutInner() {
  const { displayName, isLoading } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);

  const handleNewConversation = async () => {
    try {
      const result = await createConversation();
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setActiveId(result.conversation_id);
      navigate({ to: `/conversations/${result.conversation_id}` });
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  };

  const handleSelectConversation = (id: string) => {
    setActiveId(id);
    navigate({ to: `/conversations/${id}` });
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r bg-sidebar text-sidebar-foreground">
        {/* Header */}
        <div className="flex h-14 items-center gap-2 px-4 font-semibold border-b">
          <Bot className="h-5 w-5" />
          Claude Agent
        </div>

        {/* Conversations */}
        <div className="flex-1 overflow-hidden">
          <ConversationList
            activeConversationId={activeId}
            onSelectConversation={handleSelectConversation}
            onNewConversation={handleNewConversation}
          />
        </div>

        {/* User info */}
        <div className="p-3 border-t flex items-center gap-2 text-sm text-muted-foreground">
          <User className="h-4 w-4 flex-shrink-0" />
          {isLoading ? (
            <span className="animate-pulse">Loading...</span>
          ) : (
            <span className="truncate">{displayName}</span>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
