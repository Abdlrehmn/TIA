import { useState } from "react";
import { Sidebar } from "../components/layout/Sidebar";
import { ConversationArea } from "../components/chat/ConversationArea";
import { ChatInput } from "../components/chat/ChatInput";
import { SettingsModal } from "../components/ui/SettingsModal";
import { useConversations } from "../hooks/useConversations";

/** The single application screen: sidebar + conversation + input. */
export function ChatPage() {
  const { conversations, activeId, active, newChat, selectChat, sendMessage } =
    useConversations();
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onNewChat={newChat}
        onSelectChat={selectChat}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className="flex min-w-0 flex-1 flex-col bg-abyss">
        <header className="flex items-center justify-between gap-4 border-b border-hairline px-6 py-3">
          <h2 className="truncate text-sm font-semibold text-ink">
            {active ? active.title : "TIA"}
          </h2>
          <span className="shrink-0 rounded-full border border-hairline bg-raised/50 px-2.5 py-1 text-[11px] font-medium text-muted">
            Local · AI not connected
          </span>
        </header>
        <ConversationArea conversation={active} />
        <ChatInput onSend={sendMessage} />
      </main>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
