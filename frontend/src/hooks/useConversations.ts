import { useEffect, useState } from "react";
import type { Conversation, Message } from "../types/chat";
import { loadConversations, saveConversations } from "../lib/storage";
import { synchronizeConversations } from "../lib/api";
import { MAX_TITLE_LENGTH } from "../lib/constants";
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

function mergePersistedWithLive(persisted: Conversation[], live: Conversation[]): Conversation[] {
  const liveById = new Map(live.map((conversation) => [conversation.id, conversation]));
  const merged = persisted.map((stored) => {
    const current = liveById.get(stored.id);
    if (!current) return stored;
    const storedMessages = new Map(stored.messages.map((message) => [message.id, message]));
    const messages = current.messages.map((message) => storedMessages.get(message.id) ?? message);
    const seen = new Set(messages.map((message) => message.id));
    messages.push(...stored.messages.filter((message) => !seen.has(message.id)));
    return {
      ...stored,
      title: current.messages.length > stored.messages.length ? current.title : stored.title,
      messages,
    };
  });
  const persistedIds = new Set(persisted.map((conversation) => conversation.id));
  merged.push(...live.filter((conversation) => !persistedIds.has(conversation.id)));
  return merged;
}

/**
 * Local conversation state: messages and conversations remain persisted in
 * browser localStorage while assistant replies come from the local backend.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(
    () => loadConversations() ?? [],
  );
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const local = loadConversations() ?? [];
    void synchronizeConversations(local).then((persisted) => {
      if (cancelled) return;
      setConversations((current) => mergePersistedWithLive(persisted, current));
      setActiveId((current) => current ?? persisted[0]?.id ?? null);
    }).catch((error: unknown) => {
      console.warn("TIA: backend conversation sync failed; keeping local conversations.", error);
    });
    return () => { cancelled = true; };
  }, []);

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

  function sendMessage(text: string): { conversationId: string; messageId: string; createdAt: number } | null {
    const content = text.trim();
    if (!content) return null;

    const createdAt = Date.now();
    const messageId = uid();
    const userMessage: Message = {
      id: messageId,
      role: "user",
      content,
      createdAt,
    };
    const conversationId =
      activeId && conversations.some((conversation) => conversation.id === activeId)
        ? activeId
        : uid();

    setConversations((prev) => {
      const next = prev.some((conversation) => conversation.id === conversationId)
        ? prev
        : [{ ...makeConversation(), id: conversationId }, ...prev];
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
    return { conversationId, messageId, createdAt };
  }

  function createAssistantMessage(conversationId: string): { id: string; createdAt: number } {
    const createdAt = Date.now();
    const reply: Message = {
      id: uid(),
      role: "assistant",
      content: "",
      createdAt,
      completed: false,
    };
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, messages: [...conversation.messages, reply] }
          : conversation,
      ),
    );
    return { id: reply.id, createdAt };
  }

  function appendAssistantMessage(
    conversationId: string,
    messageId: string,
    content: string,
  ): void {
    if (!content) return;
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: conversation.messages.map((message) =>
                message.id === messageId
                  ? { ...message, content: message.content + content }
                  : message,
              ),
            }
          : conversation,
      ),
    );
  }

  function removeAssistantMessage(conversationId: string, messageId: string): void {
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: conversation.messages.filter((message) => message.id !== messageId),
            }
          : conversation,
      ),
    );
  }

  function completeAssistantMessage(conversationId: string, messageId: string): void {
    setConversations((prev) => prev.map((conversation) => conversation.id === conversationId
      ? { ...conversation, messages: conversation.messages.map((message) => message.id === messageId
        ? { ...message, completed: true }
        : message) }
      : conversation));
  }

  return {
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
  };
}
