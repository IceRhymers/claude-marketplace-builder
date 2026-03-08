import { useQuery } from "@tanstack/react-query";
import { getConversations, type Conversation } from "@/lib/api";
import { MessageSquare, PlusCircle } from "lucide-react";

interface ConversationListProps {
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

export function ConversationList({
  activeConversationId,
  onSelectConversation,
  onNewConversation,
}: ConversationListProps) {
  const { data: conversations = [], isLoading } = useQuery<Conversation[]>({
    queryKey: ["conversations"],
    queryFn: getConversations,
    refetchInterval: 30_000,
  });

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-sm font-medium"
        >
          <PlusCircle className="h-4 w-4" />
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {isLoading && (
          <div className="px-3 py-2 text-sm text-muted-foreground">
            Loading...
          </div>
        )}

        {!isLoading && conversations.length === 0 && (
          <div className="px-3 py-2 text-sm text-muted-foreground">
            No conversations yet. Start a new chat!
          </div>
        )}

        {conversations.map((conv) => {
          const isActive = conv.conversation_id === activeConversationId;
          return (
            <button
              key={conv.conversation_id}
              onClick={() => onSelectConversation(conv.conversation_id)}
              aria-selected={isActive}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors ${
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-accent/50 text-foreground"
              }`}
            >
              <MessageSquare className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">
                {conv.title || "New Conversation"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
