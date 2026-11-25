/** Typed HTTP access to the local TIA backend. */

import type { Conversation } from "../types/chat";

export interface HealthResponse {
  status: "healthy";
  app: "TIA";
  version: "0.1.0";
}

export type ApiErrorCode =
  | "aborted"
  | "http"
  | "invalid_request"
  | "invalid_json"
  | "invalid_response"
  | "network"
  | "auth_unavailable"
  | "stream"
  | "timeout";

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 5_000;
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const configuredBaseUrl = import.meta.env.VITE_TIA_API_BASE_URL?.trim();

function apiBaseUrl(value: string | undefined): string {
  if (!value) return DEFAULT_API_BASE_URL;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "http:" ||
      !["localhost", "127.0.0.1"].includes(url.hostname.toLowerCase()) ||
      url.username || url.password || url.search || url.hash
    ) {
      throw new Error("API URL must use an unauthenticated loopback HTTP origin.");
    }
    return value.replace(/\/$/, "");
  } catch (error) {
    console.warn("TIA: ignoring a non-loopback API URL override.", error);
    return DEFAULT_API_BASE_URL;
  }
}

export const API_BASE_URL = apiBaseUrl(configuredBaseUrl);

type TauriBridgeWindow = Window & {
  __TAURI__?: {
    core?: {
      invoke<T>(command: string): Promise<T>;
    };
  };
};

let apiTokenPromise: Promise<string> | null = null;

async function loadApiToken(): Promise<string> {
  const tauriInvoke = (window as TauriBridgeWindow).__TAURI__?.core?.invoke;
  let token: unknown;
  if (tauriInvoke) {
    try {
      token = await tauriInvoke<string>("get_api_token");
    } catch {
      throw new ApiError("auth_unavailable", "TIA's secure API session is unavailable.");
    }
  } else {
    throw new ApiError("auth_unavailable", "Run TIA inside its authenticated desktop session to access the local API.");
  }
  if (typeof token !== "string" || token.length < 43) {
    throw new ApiError("auth_unavailable", "TIA's secure API session is unavailable.");
  }
  return token;
}

async function getApiToken(): Promise<string> {
  if (!apiTokenPromise) apiTokenPromise = loadApiToken();
  try {
    return await apiTokenPromise;
  } catch (error) {
    apiTokenPromise = null;
    throw error;
  }
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) return false;

  const response = value as Record<string, unknown>;
  return (
    response.status === "healthy" &&
    response.app === "TIA" &&
    response.version === "0.1.0"
  );
}

async function requestJson(path: string, options: RequestOptions = {}): Promise<unknown> {
  const controller = new AbortController();
  let didTimeout = false;
  const timeoutId = window.setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  const abortRequest = () => controller.abort();
  options.signal?.addEventListener("abort", abortRequest, { once: true });

  try {
    const token = await getApiToken();
    const response = await fetch(new URL(path, `${API_BASE_URL}/`), {
      method: options.method ?? "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
      redirect: "error",
    });

    if (!response.ok) {
      throw new ApiError("http", `Backend request failed with HTTP ${response.status}.`, response.status);
    }

    try {
      return await response.json();
    } catch {
      throw new ApiError("invalid_json", "Backend returned invalid JSON.");
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (didTimeout) throw new ApiError("timeout", "Backend request timed out.");
    if (controller.signal.aborted) throw new ApiError("aborted", "Backend request was cancelled.");
    throw new ApiError("network", "Could not connect to the TIA backend.");
  } finally {
    window.clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortRequest);
  }
}

export async function getBackendHealth(options?: RequestOptions): Promise<HealthResponse> {
  const response = await requestJson("health", options);
  if (!isHealthResponse(response)) {
    throw new ApiError("invalid_response", "Backend returned an unexpected health response.");
  }
  return response;
}

export interface TestMessageResponse {
  success: true;
  message: string;
  reply: string;
}

function isTestMessageResponse(value: unknown): value is TestMessageResponse {
  if (typeof value !== "object" || value === null) return false;

  const response = value as Record<string, unknown>;
  return (
    response.success === true &&
    typeof response.message === "string" &&
    typeof response.reply === "string"
  );
}

export async function sendTestMessage(
  message: string,
  options?: RequestOptions,
): Promise<TestMessageResponse> {
  if (!message.trim()) {
    throw new ApiError("invalid_request", "Message must not be empty or whitespace.");
  }

  const response = await requestJson("api/v1/chat/test", {
    ...options,
    method: "POST",
    body: { message },
  });

  if (!isTestMessageResponse(response)) {
    throw new ApiError("invalid_response", "Backend returned an unexpected test-message response.");
  }

  return response;
}

function isConversation(value: unknown): value is Conversation {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item.id === "string" && typeof item.title === "string" &&
    typeof item.createdAt === "number" && Array.isArray(item.messages) &&
    item.messages.every((message) => typeof message === "object" && message !== null &&
      typeof (message as Record<string, unknown>).id === "string" &&
      ((message as Record<string, unknown>).role === "user" || (message as Record<string, unknown>).role === "assistant") &&
      typeof (message as Record<string, unknown>).content === "string" &&
      typeof (message as Record<string, unknown>).createdAt === "number");
}

/** Import local data first, then replace it with SQLite's persisted records. */
export async function synchronizeConversations(local: Conversation[]): Promise<Conversation[]> {
  if (local.length) {
    const importable = local.map((conversation) => ({
      id: conversation.id,
      title: conversation.title,
      createdAt: conversation.createdAt,
      messages: conversation.messages
        .filter((message) => message.role !== "assistant" || (message.completed !== false && Boolean(message.content)))
        .map(({ id, role, content, createdAt }) => ({ id, role, content, createdAt })),
    }));
    await requestJson("api/v1/conversations/import", {
      method: "POST",
      body: { conversations: importable },
      timeoutMs: 30_000,
    });
  }

  const listed = await requestJson("api/v1/conversations?limit=500");
  if (!Array.isArray(listed)) throw new ApiError("invalid_response", "Backend returned invalid conversations.");
  const records = await Promise.all(listed.map(async (item) => {
    if (typeof item !== "object" || item === null || typeof (item as Record<string, unknown>).id !== "string") {
      throw new ApiError("invalid_response", "Backend returned an invalid conversation record.");
    }
    const id = encodeURIComponent((item as Record<string, string>).id);
    const result = await requestJson(`api/v1/conversations/${id}`);
    if (!isConversation(result)) throw new ApiError("invalid_response", "Backend returned an invalid conversation.");
    return { ...result, messages: result.messages.map((message) => ({ ...message, completed: true })) };
  }));
  return records;
}

interface StreamOptions {
  signal?: AbortSignal;
  /** Maximum time without network data; reset whenever a stream chunk arrives. */
  timeoutMs?: number;
}

interface SseEvent {
  event: string;
  data: string;
}

function parseSseFrame(frame: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];

  for (const line of frame.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    const value = separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "event") event = value;
    if (field === "data") data.push(value);
  }

  return data.length > 0 ? { event, data: data.join("\n") } : null;
}

function parseSseData(event: SseEvent): Record<string, unknown> {
  let value: unknown;
  try {
    value = JSON.parse(event.data);
  } catch {
    throw new ApiError("invalid_response", "Backend returned an invalid stream event.");
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ApiError("invalid_response", "Backend returned an unexpected stream event.");
  }
  return value as Record<string, unknown>;
}

/** POST a message and incrementally deliver answer-only SSE content deltas. */
export async function streamChatMessage(
  message: string,
  onDelta: (content: string) => void,
  metadata: {
    conversation_id: string;
    user_message_id: string;
    assistant_message_id: string;
    user_created_at: number;
    assistant_created_at: number;
    conversation_created_at: number;
    conversation_title: string;
  },
  options: StreamOptions = {},
): Promise<void> {
  if (!message.trim()) {
    throw new ApiError("invalid_request", "Message must not be empty or whitespace.");
  }

  const controller = new AbortController();
  let didTimeout = false;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const resetTimeout = () => {
    if (timeoutId !== undefined) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      didTimeout = true;
      controller.abort();
    }, options.timeoutMs ?? 120_000);
  };
  const abortRequest = () => controller.abort();
  options.signal?.addEventListener("abort", abortRequest, { once: true });
  if (options.signal?.aborted) controller.abort();

  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  let finished = false;
  try {
    resetTimeout();
    let response: Response;
    try {
      const token = await getApiToken();
      response = await fetch(new URL("api/v1/chat/stream", `${API_BASE_URL}/`), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ message, ...metadata }),
        signal: controller.signal,
        redirect: "error",
      });
    } catch (error: unknown) {
      if (error instanceof ApiError) throw error;
      if (didTimeout) throw new ApiError("timeout", "The chat stream timed out.");
      if (options.signal?.aborted || controller.signal.aborted) {
        throw new ApiError("aborted", "The chat stream was cancelled.");
      }
      throw new ApiError("network", "Could not connect to the TIA backend.");
    }

    if (!response.ok) {
      try {
        await response.body?.cancel();
      } catch {
        // The server may already have closed an error response body.
      }
      throw new ApiError("http", `Backend request failed with HTTP ${response.status}.`, response.status);
    }
    if (!response.body) {
      throw new ApiError("invalid_response", "Backend did not provide a readable chat stream.");
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let receivedStart = false;
    let receivedDone = false;

    const dispatch = (frame: string) => {
      if (receivedDone) return;
      const event = parseSseFrame(frame);
      if (!event) return;
      const data = parseSseData(event);
      switch (event.event) {
        case "start":
          if (data.success !== true) {
            throw new ApiError("invalid_response", "Backend returned an invalid stream start event.");
          }
          receivedStart = true;
          break;
        case "delta":
          if (!receivedStart || typeof data.content !== "string") {
            throw new ApiError("invalid_response", "Backend returned an invalid content event.");
          }
          if (data.content) onDelta(data.content);
          break;
        case "done":
          if (data.success !== true) {
            throw new ApiError("invalid_response", "Backend returned an invalid stream completion event.");
          }
          receivedDone = true;
          break;
        case "error":
          throw new ApiError(
            "stream",
            typeof data.message === "string" && data.message
              ? data.message
              : "The local model could not complete the response.",
          );
        default:
          throw new ApiError("invalid_response", "Backend returned an unknown stream event.");
      }
    };

    while (true) {
      resetTimeout();
      let result: ReadableStreamReadResult<Uint8Array>;
      try {
        result = await reader.read();
      } catch {
        if (didTimeout) throw new ApiError("timeout", "The chat stream timed out.");
        if (options.signal?.aborted || controller.signal.aborted) {
          throw new ApiError("aborted", "The chat stream was cancelled.");
        }
        throw new ApiError("network", "The chat stream connection was interrupted.");
      }

      if (result.done) {
        buffer += decoder.decode();
        if (buffer.trim() && !receivedDone) dispatch(buffer);
        break;
      }

      buffer += decoder.decode(result.value, { stream: true });
      while (true) {
        const separator = /\r?\n\r?\n/.exec(buffer);
        if (!separator || separator.index === undefined) break;
        dispatch(buffer.slice(0, separator.index));
        buffer = buffer.slice(separator.index + separator[0].length);
      }
    }

    if (!receivedStart || !receivedDone) {
      throw new ApiError("invalid_response", "The chat stream ended before a complete response arrived.");
    }
    finished = true;
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortRequest);
    if (reader) {
      if (!finished) {
        try {
          await reader.cancel();
        } catch {
          // The stream may already be closed by cancellation or a network failure.
        }
      }
      reader.releaseLock();
    }
  }
}
