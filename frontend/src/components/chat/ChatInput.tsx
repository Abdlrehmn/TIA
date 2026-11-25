import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { Mic, SendHorizontal, Square } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  isSending: boolean;
}

/**
 * Bottom input bar: working text input + send button, and the microphone
 * button as a visual placeholder only (voice input arrives in a later
 * phase, so it is rendered disabled with an honest tooltip).
 */
export function ChatInput({ onSend, onStop, isSending }: ChatInputProps) {
  const [text, setText] = useState("");
  const canSend = text.trim().length > 0;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSend(text);
    setText("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="border-t border-hairline px-6 py-4">
      <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isSending}
          rows={1}
          placeholder="Message TIA… (English or Roman Urdu)"
          aria-label="Message input"
          className="max-h-40 flex-1 resize-none rounded-xl border border-hairline bg-surface px-4 py-3 text-sm text-ink focus:border-accent/50 focus:outline-none placeholder:text-faint"
        />
        {isSending ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop generation"
            title="Stop generation"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-accent/40 bg-accent/15 text-accent transition-colors hover:bg-accent/25"
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-accent/40 bg-accent/15 text-accent transition-colors hover:bg-accent/25 disabled:cursor-not-allowed disabled:border-hairline disabled:bg-raised/50 disabled:text-faint"
          >
            <SendHorizontal size={18} />
          </button>
        )}
        <button
          type="button"
          disabled
          title="Microphone input is not implemented yet — coming in a later phase."
          aria-label="Microphone (not implemented yet)"
          className="flex h-11 w-11 shrink-0 cursor-not-allowed items-center justify-center rounded-xl border border-hairline bg-raised/50 text-faint"
        >
          <Mic size={18} />
        </button>
      </div>
      {isSending && (
        <p role="status" className="mx-auto mt-2 w-full max-w-3xl text-[11px] text-accent">
          Generating response...
        </p>
      )}
      <p className="mx-auto mt-2 w-full max-w-3xl text-[11px] text-faint">
        Enter to send · Shift+Enter for a new line
      </p>
    </form>
  );
}
