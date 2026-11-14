import { useEffect, useState } from "react";
import type { Conversation, Message } from "../types/chat";
import { loadConversations, saveConversations } from "../lib/storage";
import { MAX_TITLE_LENGTH, PLACEHOLDER_REPLY } from "../lib/constants";
import { uid } from "../lib/uid";

function makeConversation(): Conversation {
  return { id: uid(), title: "New chat", createdAt: Date.now(), messages: [] };
}

/** Derive a conversation title from its first user message. */
function titleFrom(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  return trimmed.length <= MAX_TITLE_LENGTH
    ? trimmed
    : trimmed.slice(0, MAX_TITLE_LENGTH - 1) + "…";
}

/**
 * Local conversation state for Phase 1: create chats, send messages and
 * get an honest placeholder reply. Persistence is browser-local only;
 * the backend phase will replace this with API calls + SQLite storage.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(
    () => loadConversations() ?? [],
  );
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    saveConversations(conversations);
  }, [conversations]);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  function newChat(): void {
    // Reuse an existing empty chat instead of piling up blank ones.
    const empty = conversations.find((c) => c.messages.length === 0);
    if (empty) {
      setActiveId(empty.id);
      return;
    }
    const conversation = makeConversation();
    setConversations((prev) => [conversation, ...prev]);
    setActiveId(conversation.id);
  }

  function selectChat(id: string): void {
    setActiveId(id);
  }

  function sendMessage(text: string): void {
    const content = text.trim();
    if (!content) return;

    const userMessage: Message = {
      id: uid(),
      role: "user",
      content,
      createdAt: Date.now(),
    };
    let conversationId = activeId;

    setConversations((prev) => {
      let next = prev;
      // No active chat yet: create one implicitly so text input works on day one.
      if (!conversationId || !prev.some((c) => c.id === conversationId)) {
        const conversation = makeConversation();
        conversationId = conversation.id;
        next = [conversation, ...prev];
      }
      return next.map((c) =>
        c.id === conversationId
          ? {
              ...c,
              title: c.messages.length === 0 ? titleFrom(content) : c.title,
              messages: [...c.messages, userMessage],
            }
          : c,
      );
    });
    setActiveId(conversationId);

    // Honest placeholder "reply" so the input does something real today.
    window.setTimeout(() => {
      const reply: Message = {
        id: uid(),
        role: "assistant",
        content: PLACEHOLDER_REPLY,
        createdAt: Date.now(),
      };
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId ? { ...c, messages: [...c.messages, reply] } : c,
        ),
      );
    }, 600);
  }

  return { conversations, activeId, active, newChat, selectChat, sendMessage };
}
