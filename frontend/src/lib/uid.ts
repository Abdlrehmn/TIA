/** Generate a unique id for conversations and messages. */
export function uid(): string {
  return crypto.randomUUID();
}
