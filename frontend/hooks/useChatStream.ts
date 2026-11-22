"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEFAULT_ENDPOINT = `${API_URL}/chat/stream`;

export type ChatStreamStatus =
  "idle" | "connecting" | "streaming" | "reconnecting" | "done" | "error" | "aborted";

export interface ChatStreamMeta {
  session_id: string;
  user_message_id: string | null;
  message_id: string | null;
  question: string;
  rewritten_query: string;
  rewrite_source: string;
  depends_on_context: boolean;
  conversation_tokens: number;
  conversation_messages: number;
  summary_used: boolean;
  replayed: boolean;
  prepare_ms: number;
}

export interface ChatCitation {
  source: string;
  quote: string;
}

export interface ChatStreamCitations {
  items: ChatCitation[];
  citation_validity: number;
  unmatched: { citation: string; reason: string }[];
  warnings: string[];
}

export interface ChatStreamDone {
  session_id?: string;
  message_id: string | null;
  status: string;
  replayed?: boolean;
  latency_ms?: number;
  ttft_ms?: number | null;
  usage?: { input_tokens: number; output_tokens: number };
  provider?: string;
  model?: string;
  fallback_used?: string | null;
  confidence?: number;
  abstained?: boolean;
  abstention_type?: string;
}

export interface ChatStreamError {
  code: string;
  message: string;
  message_id?: string | null;
}

export interface SendChatOptions {
  question: string;
  sessionId?: string | null;
  requestId?: string;
}

export interface UseChatStreamOptions {
  endpoint?: string;
  getAccessToken?: () => string | null | Promise<string | null>;
  maxRetries?: number;
  retryDelayMs?: number;
  fetchImpl?: typeof fetch;
}

export interface UseChatStreamResult {
  status: ChatStreamStatus;
  answer: string;
  citations: ChatStreamCitations | null;
  meta: ChatStreamMeta | null;
  done: ChatStreamDone | null;
  error: ChatStreamError | null;
  sessionId: string | null;
  requestId: string | null;
  reconnectAttempt: number;
  send: (options: SendChatOptions) => Promise<void>;
  cancel: () => void;
  reset: () => void;
}

interface SseFrame {
  event: string;
  data: string;
}

class ChatStreamRequestError extends Error {
  readonly code: string;
  readonly transient: boolean;

  constructor(message: string, code: string, transient: boolean) {
    super(message);
    this.name = "ChatStreamRequestError";
    this.code = code;
    this.transient = transient;
  }
}

function parseFrame(block: string): SseFrame | null {
  let event = "message";
  const data: string[] = [];
  for (const rawLine of block.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(":")) {
      continue;
    }
    const colon = rawLine.indexOf(":");
    const field = colon === -1 ? rawLine : rawLine.slice(0, colon);
    let value = colon === -1 ? "" : rawLine.slice(colon + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    if (field === "event") {
      event = value;
    } else if (field === "data") {
      data.push(value);
    }
  }
  if (data.length === 0) {
    return null;
  }
  return { event, data: data.join("\n") };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function readString(value: unknown, key: string): string | null {
  const record = asRecord(value);
  const field = record?.[key];
  return typeof field === "string" ? field : null;
}

function parseStreamError(payload: unknown): ChatStreamError {
  return {
    code: readString(payload, "code") ?? "stream_error",
    message: readString(payload, "message") ?? "Luồng trả lời gặp lỗi.",
    message_id: readString(payload, "message_id"),
  };
}

async function responseError(response: Response): Promise<ChatStreamRequestError> {
  let code = `http_${response.status}`;
  let message = `Máy chủ trả HTTP ${response.status}.`;
  try {
    const body: unknown = await response.json();
    const detail = asRecord(asRecord(body)?.detail) ?? asRecord(body);
    code = readString(detail, "code") ?? code;
    message = readString(detail, "message") ?? message;
  } catch {
    // Phản hồi lỗi không phải JSON: giữ thông báo mặc định.
  }
  return new ChatStreamRequestError(message, code, response.status >= 500);
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Đã hủy", "AbortError"));
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new DOMException("Đã hủy", "AbortError"));
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export function useChatStream(options: UseChatStreamOptions = {}): UseChatStreamResult {
  const {
    endpoint = DEFAULT_ENDPOINT,
    getAccessToken,
    maxRetries = 2,
    retryDelayMs = 600,
    fetchImpl,
  } = options;

  const [status, setStatus] = useState<ChatStreamStatus>("idle");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<ChatStreamCitations | null>(null);
  const [meta, setMeta] = useState<ChatStreamMeta | null>(null);
  const [done, setDone] = useState<ChatStreamDone | null>(null);
  const [error, setError] = useState<ChatStreamError | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

  useEffect(() => () => abortRef.current?.abort(), []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("aborted");
  }, []);

  const reset = useCallback(() => {
    runIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setAnswer("");
    setCitations(null);
    setMeta(null);
    setDone(null);
    setError(null);
    setSessionId(null);
    setRequestId(null);
    setReconnectAttempt(0);
  }, []);

  const send = useCallback(
    async (sendOptions: SendChatOptions) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const runId = ++runIdRef.current;
      const request = sendOptions.requestId ?? crypto.randomUUID();
      const state = { sessionId: sendOptions.sessionId ?? null, sawDone: false };

      setStatus("connecting");
      setAnswer("");
      setCitations(null);
      setMeta(null);
      setDone(null);
      setError(null);
      setRequestId(request);
      setSessionId(sendOptions.sessionId ?? null);
      setReconnectAttempt(0);

      const update = (fn: () => void) => {
        if (runIdRef.current === runId && !controller.signal.aborted) {
          fn();
        }
      };

      for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
        if (controller.signal.aborted) {
          return;
        }
        update(() => {
          setStatus(attempt === 0 ? "connecting" : "reconnecting");
          setReconnectAttempt(attempt);
          if (attempt > 0) {
            setAnswer("");
            setCitations(null);
            setMeta(null);
            setDone(null);
            setError(null);
          }
        });
        state.sawDone = false;

        try {
          const headers: Record<string, string> = {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            "Cache-Control": "no-cache",
          };
          const token = await getAccessToken?.();
          if (token) {
            headers.Authorization = `Bearer ${token}`;
          }

          const response = await (fetchImpl ?? fetch)(endpoint, {
            method: "POST",
            headers,
            body: JSON.stringify({
              question: sendOptions.question,
              session_id: state.sessionId,
              request_id: request,
            }),
            signal: controller.signal,
          });
          if (!response.ok) {
            throw await responseError(response);
          }
          if (!response.body) {
            throw new ChatStreamRequestError(
              "Trình duyệt không đọc được luồng trả lời.",
              "stream_unavailable",
              false,
            );
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          const handleFrame = (block: string) => {
            const frame = parseFrame(block);
            if (!frame) {
              return;
            }
            let payload: unknown;
            try {
              payload = JSON.parse(frame.data);
            } catch {
              throw new ChatStreamRequestError(
                "Sự kiện trả về không đúng định dạng.",
                "invalid_event",
                false,
              );
            }
            if (frame.event === "meta") {
              const nextSession = readString(payload, "session_id");
              if (nextSession) {
                state.sessionId = nextSession;
              }
              update(() => {
                setMeta(payload as ChatStreamMeta);
                setSessionId(nextSession ?? state.sessionId);
              });
            } else if (frame.event === "token") {
              const text = readString(payload, "text");
              if (text) {
                update(() => {
                  setStatus("streaming");
                  setAnswer((current) => current + text);
                });
              }
            } else if (frame.event === "citations") {
              update(() => setCitations(payload as ChatStreamCitations));
            } else if (frame.event === "done") {
              state.sawDone = true;
              const payloadRecord = asRecord(payload);
              const finished = payloadRecord?.status === "complete";
              update(() => {
                setDone(payload as ChatStreamDone);
                setStatus(finished ? "done" : "error");
              });
            } else if (frame.event === "error") {
              update(() => setError(parseStreamError(payload)));
            }
          };

          while (!controller.signal.aborted) {
            const { done: ended, value } = await reader.read();
            if (ended) {
              buffer += decoder.decode();
              break;
            }
            buffer += decoder.decode(value, { stream: true });
            let boundary = buffer.indexOf("\n\n");
            while (boundary !== -1) {
              const block = buffer.slice(0, boundary);
              buffer = buffer.slice(boundary + 2);
              handleFrame(block);
              boundary = buffer.indexOf("\n\n");
            }
          }
          if (buffer.trim()) {
            handleFrame(buffer);
          }
          if (controller.signal.aborted) {
            return;
          }
          if (!state.sawDone) {
            throw new ChatStreamRequestError(
              "Luồng trả lời bị ngắt trước khi hoàn tất.",
              "stream_truncated",
              true,
            );
          }
          return;
        } catch (caught) {
          if (controller.signal.aborted) {
            return;
          }
          const isAbort = caught instanceof DOMException && caught.name === "AbortError";
          if (isAbort) {
            return;
          }
          const transient =
            caught instanceof ChatStreamRequestError
              ? caught.transient
              : caught instanceof TypeError;
          if (transient && attempt < maxRetries) {
            try {
              await sleep(retryDelayMs * 2 ** attempt, controller.signal);
            } catch {
              return;
            }
            continue;
          }
          const streamError =
            caught instanceof ChatStreamRequestError
              ? caught
              : new ChatStreamRequestError("Không kết nối được máy chủ.", "network_error", true);
          update(() => {
            setError({ code: streamError.code, message: streamError.message });
            setStatus("error");
            setReconnectAttempt(0);
          });
          return;
        }
      }
    },
    [endpoint, getAccessToken, maxRetries, retryDelayMs, fetchImpl],
  );

  return {
    status,
    answer,
    citations,
    meta,
    done,
    error,
    sessionId,
    requestId,
    reconnectAttempt,
    send,
    cancel,
    reset,
  };
}
