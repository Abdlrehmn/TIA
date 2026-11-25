import type { Message } from "../../types/chat";
import { formatTime } from "../../lib/time";
import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Orb } from "../ui/Orb";

const markdownComponents: Components = {
  a({ href, children }) {
    if (!href) return <span>{children}</span>;

    const isExternal = /^https?:/i.test(href) || href.startsWith("//");
    return (
      <a
        href={href}
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noopener noreferrer" : undefined}
        className="text-accent underline underline-offset-2 hover:text-ink"
      >
        {children}
      </a>
    );
  },
  h1: ({ children }) => <h1 className="mb-2 mt-4 text-lg font-semibold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-4 text-base font-semibold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1 mt-3 text-sm font-semibold first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1 mt-3 text-sm font-semibold first:mt-0">{children}</h4>,
  h5: ({ children }) => <h5 className="mb-1 mt-2 text-sm font-semibold first:mt-0">{children}</h5>,
  h6: ({ children }) => <h6 className="mb-1 mt-2 text-sm font-semibold first:mt-0">{children}</h6>,
  p: ({ children }) => <p className="my-2 leading-relaxed first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-accent/50 pl-3 text-muted">
      {children}
    </blockquote>
  ),
  code: ({ children }) => (
    <code className="rounded bg-raised px-1 py-0.5 font-mono text-[0.85em] text-accent">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-3 max-w-full overflow-x-auto rounded-lg border border-hairline bg-deep p-3 text-xs leading-relaxed [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-inherit">
      {children}
    </pre>
  ),
  table: ({ children, node, ...props }) => {
    void node;
    return (
      <div className="my-3 max-w-full overflow-x-auto">
        <table
          {...props}
          className="w-full border-collapse text-left text-xs [&_td]:border [&_td]:border-hairline [&_td]:px-2 [&_td]:py-1.5 [&_th]:border [&_th]:border-hairline [&_th]:bg-raised [&_th]:px-2 [&_th]:py-1.5"
        >
          {children}
        </table>
      </div>
    );
  },
};

interface MessageBubbleProps {
  message: Message;
}

/** A single chat message: user (right, cyan tint) or TIA (left, navy). */
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex w-full gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && <Orb size={28} className="mt-1" />}
      <div
        className={`max-w-[70%] rounded-2xl border px-4 py-2.5 ${
          isUser ? "border-accent/30 bg-accent/10" : "border-hairline bg-surface"
        }`}
      >
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-ink">
            {message.content}
          </p>
        ) : (
          <div className="min-w-0 break-words text-sm text-ink [&_pre_code]:whitespace-pre">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
              skipHtml
              urlTransform={(url) => defaultUrlTransform(url) || undefined}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        <p
          className={`mt-1 text-[10px] ${
            isUser ? "text-right text-accent/50" : "text-faint"
          }`}
        >
          {formatTime(message.createdAt)}
        </p>
      </div>
    </div>
  );
}
