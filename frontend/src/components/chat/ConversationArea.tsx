import type { Conversation } from "../../types/chat";
import { useAutoScroll } from "../../hooks/useAutoScroll";
import { MessageBubble } from "./MessageBubble";
import { WelcomeMessage } from "./WelcomeMessage";

interface ConversationAreaProps {
  conversation: Conversation | null;
}

/** Main conversation region: welcome state or the scrollable message list. */
export function ConversationArea({ conversation }: ConversationAreaProps) {
  const messageCount = conversation?.messages.length ?? 0;
  const scrollRef = useAutoScroll<HTMLDivElement>(messageCount);

  return (
    <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
      {messageCount === 0 ? (
        <WelcomeMessage />
      ) : (
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-6">
          {conversation?.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>
      )}
    </div>
  );
}
