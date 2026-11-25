/** Core chat data types. The backend phase will map these to its API models. */

export type Role = "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  /** False while streamed locally; absent means a legacy completed message. */
  completed?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  messages: Message[];
}
