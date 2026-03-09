import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolCallBadgeProps {
  tool: string;
  input?: unknown;
  output?: string;
  variant?: "use" | "result";
}

export function ToolCallBadge({ tool, input, output, variant = "use" }: ToolCallBadgeProps) {
  const [expanded, setExpanded] = useState(false);

  const hasDetails = (variant === "use" && input !== undefined) || (variant === "result" && output !== undefined);
  const detailContent = variant === "use"
    ? JSON.stringify(input, null, 2)
    : output;

  return (
    <div
      data-testid={`tool-call-badge-${variant}`}
      className={cn(
        "my-1 inline-flex flex-col rounded-md border text-xs font-mono",
        variant === "use"
          ? "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200"
          : "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
      )}
    >
      <button
        onClick={() => hasDetails && setExpanded((v) => !v)}
        className={cn(
          "flex items-center gap-1.5 px-2 py-1",
          hasDetails ? "cursor-pointer" : "cursor-default"
        )}
        aria-expanded={expanded}
      >
        <Wrench className="h-3 w-3 flex-shrink-0" />
        <span className="font-semibold">{variant === "use" ? "Tool call:" : "Tool result:"}</span>
        <span>{tool}</span>
        {hasDetails && (
          expanded
            ? <ChevronDown className="h-3 w-3 ml-auto" />
            : <ChevronRight className="h-3 w-3 ml-auto" />
        )}
      </button>

      {expanded && detailContent && (
        <pre className="border-t px-2 py-1 text-xs whitespace-pre-wrap overflow-auto max-h-40">
          {detailContent}
        </pre>
      )}
    </div>
  );
}
