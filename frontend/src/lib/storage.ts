import type { Conversation } from "../types/chat";
import { STORAGE_KEY } from "./constants";

/**
 * Local persistence for conversations (browser localStorage inside the
 * Tauri window). Deliberately simple: real storage moves to SQLite in a
 * later phase together with the backend.
 */
export function loadConversations(): Conversation[] | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Conversation[];
    if (!Array.isArray(parsed)) return null;
    return parsed;
  } catch (error) {
    console.warn("TIA: could not read saved conversations, starting fresh.", error);
    return null;
  }
}

export function saveConversations(conversations: Conversation[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch (error) {
    console.warn("TIA: could not save conversations locally.", error);
  }
}
