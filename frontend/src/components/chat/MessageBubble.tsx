import type { Message } from "../../types/chat";
import { formatTime } from "../../lib/time";
import { Orb } from "../ui/Orb";

interface MessageBubbleProps {
  message: Message;
}

/** A single chat message: user (right, cyan tint) or TIA (left, navy). */
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex w-full gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && <Orb size={28} className="mt-1" />}
      <div
        className={`max-w-[70%] rounded-2xl border px-4 py-2.5 ${
          isUser ? "border-accent/30 bg-accent/10" : "border-hairline bg-surface"
        }`}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink">
          {message.content}
        </p>
        <p
          className={`mt-1 text-[10px] ${
            isUser ? "text-right text-accent/50" : "text-faint"
          }`}
        >
          {formatTime(message.createdAt)}
        </p>
      </div>
    </div>
  );
}
