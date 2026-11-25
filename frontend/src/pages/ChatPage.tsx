import { useRef, useState } from "react";
import { Sidebar } from "../components/layout/Sidebar";
import { ConversationArea } from "../components/chat/ConversationArea";
import { ChatInput } from "../components/chat/ChatInput";
import { SettingsModal } from "../components/ui/SettingsModal";
import { useBackendHealth } from "../hooks/useBackendHealth";
import { useConversations } from "../hooks/useConversations";
import { ApiError, streamChatMessage } from "../lib/api";

function replyForApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "The backend request failed unexpectedly. Please try again.";
  }

  switch (error.code) {
    case "network":
      return "I couldn't connect to the backend. Check that it is running, then try again.";
    case "auth_unavailable":
      return "TIA's local API session is unavailable. Restart TIA and try again.";
    case "http":
      if (error.status === 401 || error.status === 403) {
        return "TIA could not authenticate with its local backend. Restart TIA's development launcher and try again.";
      }
      if (error.status === 503) {
        return "TIA's local AI is unavailable. Make sure Ollama is running, then try again.";
      }
      return error.status === 422
        ? "The backend rejected this message. Please check it and try again."
        : `The backend request failed (HTTP ${error.status ?? "unknown"}). Please try again.`;
    case "timeout":
      return "The backend took too long to respond. Please try again.";
    case "invalid_json":
    case "invalid_response":
      return "The backend returned an invalid response. Please try again later.";
    case "aborted":
      return "The backend request was cancelled.";
    case "invalid_request":
      return "Please enter a message before sending it.";
    case "stream":
      return error.message;
  }
}

/** The single application screen: sidebar + conversation + input. */
export function ChatPage() {
  const {
    conversations,
    activeId,
    active,
    newChat,
    selectChat,
    sendMessage,
    createAssistantMessage,
    appendAssistantMessage,
    removeAssistantMessage,
    completeAssistantMessage,
  } = useConversations();
  const { state: backendState } = useBackendHealth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const requestInProgress = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);

  function handleSend(text: string): void {
    if (requestInProgress.current) return;

    const turn = sendMessage(text);
    if (!turn) return;
    const conversationId = turn.conversationId;
    const activeConversationId = conversationId;
    const assistant = createAssistantMessage(activeConversationId);
    const assistantMessageId = assistant.id;
    const controller = new AbortController();

    requestInProgress.current = true;
    activeRequest.current = controller;
    setIsSending(true);

    let pendingContent = "";
    let receivedContent = "";
    let animationFrame: number | null = null;

    function flushContent(): void {
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
        animationFrame = null;
      }
      if (!pendingContent) return;
      const content = pendingContent;
      pendingContent = "";
      receivedContent += content;
      appendAssistantMessage(activeConversationId, assistantMessageId, content);
    }

    function queueContent(content: string): void {
      pendingContent += content;
      if (animationFrame === null) {
        animationFrame = window.requestAnimationFrame(flushContent);
      }
    }

    void streamChatMessage(text.trim(), queueContent, {
      conversation_id: conversationId,
      user_message_id: turn.messageId,
      assistant_message_id: assistantMessageId,
      user_created_at: turn.createdAt,
      assistant_created_at: assistant.createdAt,
      conversation_created_at: active?.createdAt ?? turn.createdAt,
      conversation_title: active && active.messages.length > 0
        ? active.title
        : text.trim().slice(0, 200),
    }, {
      signal: controller.signal,
      timeoutMs: 120_000,
    })
      .then(() => {
        // streamChatMessage resolves only after a complete SSE done event.
        completeAssistantMessage(activeConversationId, assistantMessageId);
      })
      .catch((error: unknown) => {
        flushContent();
        if (error instanceof ApiError && error.code === "aborted") {
          if (!receivedContent) removeAssistantMessage(activeConversationId, assistantMessageId);
          return;
        }
        console.warn("TIA backend chat stream failed:", error);
        const errorMessage = replyForApiError(error);
        appendAssistantMessage(
          activeConversationId,
          assistantMessageId,
          receivedContent ? `\n\n${errorMessage}` : errorMessage,
        );
      })
      .finally(() => {
        flushContent();
        if (activeRequest.current === controller) activeRequest.current = null;
        requestInProgress.current = false;
        setIsSending(false);
      });
  }

  function stopGeneration(): void {
    activeRequest.current?.abort();
  }

  const backendLabel =
    backendState === "online"
      ? "Backend online"
      : backendState === "offline"
        ? "Backend offline"
        : "Backend checking";

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
            {backendLabel}
          </span>
          <span className="shrink-0 rounded-full border border-hairline bg-raised/50 px-2.5 py-1 text-[11px] font-medium text-muted">
            Local · AI
          </span>
        </header>
        <ConversationArea conversation={active} />
        <ChatInput onSend={handleSend} onStop={stopGeneration} isSending={isSending} />
      </main>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
