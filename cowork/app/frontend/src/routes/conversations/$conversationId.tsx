import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { getMessages, type Message } from "@/lib/api";
import { streamMessage, type StreamEvent } from "@/lib/stream";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { Bot } from "lucide-react";

export const Route = createFileRoute("/conversations/$conversationId")({
  component: ConversationPageRoute,
});

interface StreamingMessage {
  role: "assistant";
  content: string;
  isStreaming: boolean;
}

// Route wrapper — pulls conversationId from router params
function ConversationPageRoute() {
  const { conversationId } = Route.useParams();
  return <ConversationPage conversationId={conversationId} />;
}

// Named export for testing — accepts conversationId as a prop
export function ConversationPage({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [streamingMsg, setStreamingMsg] = useState<StreamingMessage | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const { data: messages = [], isLoading } = useQuery<Message[]>({
    queryKey: ["messages", conversationId],
    queryFn: () => getMessages(conversationId),
    enabled: !!conversationId,
  });

  const handleSend = async (text: string) => {
    if (isStreaming) return;

    setIsStreaming(true);
    setStreamingMsg({ role: "assistant", content: "", isStreaming: true });

    let accumulatedText = "";

    try {
      await streamMessage(conversationId, text, (event: StreamEvent) => {
        if (event.type === "text_delta") {
          accumulatedText += event.text;
          setStreamingMsg({ role: "assistant", content: accumulatedText, isStreaming: true });
          // Scroll to bottom on new content
          bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        } else if (event.type === "done") {
          setStreamingMsg(null);
          setIsStreaming(false);
          // Refresh message history
          queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
          queryClient.invalidateQueries({ queryKey: ["conversations"] });
        } else if (event.type === "error") {
          setStreamingMsg(null);
          setIsStreaming(false);
        }
      });
    } catch (err) {
      console.error("Stream error:", err);
      setStreamingMsg(null);
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && (
          <div className="flex justify-center py-8">
            <Bot className="h-8 w-8 animate-pulse text-muted-foreground" />
          </div>
        )}

        {!isLoading && messages.length === 0 && !streamingMsg && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-16">
            <Bot className="h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">
              Send a message to start the conversation.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            role={msg.role}
            content={msg.content}
            createdAt={msg.created_at}
          />
        ))}

        {streamingMsg && (
          <MessageBubble
            role={streamingMsg.role}
            content={streamingMsg.content + (streamingMsg.isStreaming ? "▊" : "")}
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} isStreaming={isStreaming} />
    </div>
  );
}
