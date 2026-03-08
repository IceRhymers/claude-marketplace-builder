import Markdown from "react-markdown";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
}

export function MessageBubble({ role, content, createdAt }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      data-role={role}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <Markdown>{content}</Markdown>
          </div>
        )}
        {createdAt && (
          <p className="text-xs opacity-60 mt-1">
            {new Date(createdAt).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}
