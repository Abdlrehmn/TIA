import { MessageSquarePlus, Settings } from "lucide-react";
import type { Conversation } from "../../types/chat";
import { formatTime } from "../../lib/time";
import { Orb } from "../ui/Orb";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onNewChat: () => void;
  onSelectChat: (id: string) => void;
  onOpenSettings: () => void;
}

/** Left navigation: branding, New Chat, conversation history, Settings. */
export function Sidebar({
  conversations,
  activeId,
  onNewChat,
  onSelectChat,
  onOpenSettings,
}: SidebarProps) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-hairline bg-deep">
      <div className="flex items-center gap-3 px-4 pt-5 pb-4">
        <Orb size={38} />
        <div>
          <div className="text-[15px] font-bold text-ink">TIA</div>
          <div className="text-[11px] text-faint">Personal AI Desktop Agent</div>
        </div>
      </div>

      <div className="px-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-accent/30 bg-accent/10 px-3 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
        >
          <MessageSquarePlus size={16} />
          New Chat
        </button>
      </div>

      <div className="mt-5 px-4 text-[11px] font-semibold tracking-wider text-faint uppercase">
        Conversation History
      </div>
      <nav className="mt-2 flex-1 space-y-1 overflow-y-auto px-2 pb-4" aria-label="Conversation history">
        {conversations.length === 0 ? (
          <p className="px-2 py-3 text-xs text-faint">
            No conversations yet. Start a new chat!
          </p>
        ) : (
          conversations.map((conversation) => (
            <button
              key={conversation.id}
              onClick={() => onSelectChat(conversation.id)}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                conversation.id === activeId
                  ? "bg-raised text-ink"
                  : "text-muted hover:bg-raised/60 hover:text-ink"
              }`}
            >
              <div className="truncate">{conversation.title}</div>
              <div className="text-[11px] text-faint">
                {formatTime(conversation.createdAt)}
              </div>
            </button>
          ))
        )}
      </nav>

      <div className="border-t border-hairline p-3">
        <button
          onClick={onOpenSettings}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-raised/60 hover:text-ink"
        >
          <Settings size={16} />
          Settings
        </button>
        <p className="mt-2 px-3 text-[11px] text-faint">v0.1.0 · Local &amp; private</p>
      </div>
    </aside>
  );
}
