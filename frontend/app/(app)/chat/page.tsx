"use client";

import { useSearchParams } from "next/navigation";
import {
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { CitationChips } from "@/components/Citations";
import { Markdown } from "@/components/Markdown";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  PageHeader,
  Spinner,
  Textarea,
  cn,
} from "@/components/ui";
import { useChatStream } from "@/hooks/useChatStream";
import { apiRequest, getAccessToken } from "@/lib/api";
import { savePreferences, usePreferences } from "@/lib/preferences";
import type {
  AppMeta,
  AnswerMode,
  ChatMessage,
  Citation,
  MessageList,
} from "@/lib/types";

interface Entry {
  key: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  aborted?: boolean;
}

const SUGGESTIONS = [
  "Khi nào nên dùng S3 Glacier Deep Archive thay vì S3 Standard-IA?",
  "So sánh Multi-AZ và Read Replica cho cơ sở dữ liệu RDS.",
  "Thiết kế kiến trúc tiết kiệm chi phí cho workload có lưu lượng theo mùa.",
];

const ACTIVE_STATUSES = new Set(["connecting", "streaming", "reconnecting"]);

function toEntries(messages: ChatMessage[]): Entry[] {
  return messages.map((message) => ({
    key: message.id,
    role: message.role === "user" ? "user" : "assistant",
    content: message.content,
    citations: Array.isArray(message.citations) ? message.citations : [],
  }));
}

function ChatView({ initialSessionId }: { initialSessionId: string | null }) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const pendingRef = useRef<string | null>(null);
  const committedRef = useRef<string | null>(null);
  const abortedRef = useRef<string | null>(null);
  const historySeqRef = useRef(0);
  const [composer, setComposer] = useState("");
  const preferences = usePreferences();
  const [meta, setMeta] = useState<AppMeta | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(Boolean(initialSessionId));
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  const stream = useChatStream({ getAccessToken });
  const busy = ACTIVE_STATUSES.has(stream.status);
  const maxChars = meta?.max_question_chars ?? 4000;

  useEffect(() => {
    apiRequest<AppMeta>("/meta")
      .then(setMeta)
      .catch(() => setMetaError(true));
  }, []);

  useEffect(() => {
    if (!initialSessionId) {
      return;
    }
    const seq = ++historySeqRef.current;
    apiRequest<MessageList>(`/sessions/${initialSessionId}/messages`)
      .then((data) => {
        if (seq !== historySeqRef.current) {
          return;
        }
        setEntries(toEntries(data.items));
        setHistoryError(null);
      })
      .catch((caught: unknown) => {
        if (seq !== historySeqRef.current) {
          return;
        }
        setHistoryError(
          caught instanceof Error ? caught.message : "Không tải được cuộc trò chuyện này.",
        );
      })
      .finally(() => {
        if (seq === historySeqRef.current) {
          setLoadingHistory(false);
        }
      });
    return () => {
      historySeqRef.current += 1;
    };
  }, [initialSessionId, historyKey]);

  // Không đồng bộ URL khi đang stream: Next App Router xử lý replaceState như một
  // điều hướng mềm, remount trang và hủy request SSE giữa chừng.
  useEffect(() => {
    if (stream.status !== "done" || !stream.requestId) {
      return;
    }
    if (committedRef.current === stream.requestId) {
      return;
    }
    committedRef.current = stream.requestId;
    const question = pendingRef.current;
    pendingRef.current = null;
    setPendingQuestion(null);
    if (!question) {
      return;
    }
    const citations = stream.citations?.items ?? [];
    setEntries((previous) => [
      ...previous,
      { key: `user-${stream.requestId}`, role: "user", content: question, citations: [] },
      {
        key: `assistant-${stream.requestId}`,
        role: "assistant",
        content: stream.answer,
        citations,
      },
    ]);
  }, [stream.status, stream.requestId, stream.answer, stream.citations]);

  useEffect(() => {
    if (stream.status !== "aborted") {
      return;
    }
    const question = pendingRef.current;
    if (!question) {
      return;
    }
    const guardKey = stream.requestId ?? question;
    if (abortedRef.current === guardKey) {
      return;
    }
    abortedRef.current = guardKey;
    const citations = stream.citations?.items ?? [];
    pendingRef.current = null;
    setPendingQuestion(null);
    const key = `aborted-${Date.now()}`;
    setEntries((previous) => [
      ...previous,
      { key: `${key}-user`, role: "user", content: question, citations: [] },
      {
        key: `${key}-assistant`,
        role: "assistant",
        content: stream.answer,
        citations,
        aborted: true,
      },
    ]);
  }, [stream.status, stream.answer, stream.citations, stream.requestId]);

  useEffect(() => {
    const distance =
      document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
    if (distance < 320) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [entries.length, pendingQuestion, stream.answer.length]);

  const submit = useCallback(
    (raw: string) => {
      const question = raw.trim();
      if (!question || busy) {
        return;
      }
      setComposer("");
      setPendingQuestion(question);
      pendingRef.current = question;
      void stream.send({
        question,
        sessionId: stream.sessionId ?? sessionId,
        mode: preferences.mode,
        language: preferences.language,
        model: preferences.model || undefined,
      });
    },
    [busy, preferences, sessionId, stream],
  );

  const startNewChat = useCallback(() => {
    stream.reset();
    historySeqRef.current += 1;
    committedRef.current = null;
    pendingRef.current = null;
    setPendingQuestion(null);
    setEntries([]);
    setSessionId(null);
    setHistoryError(null);
    setLoadingHistory(false);
    setComposer("");
    window.history.replaceState(null, "", "/chat");
  }, [stream]);

  const setMode = (mode: AnswerMode) => {
    savePreferences({ ...preferences, mode });
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit(composer);
    }
  };

  const retry = () => {
    if (!pendingRef.current) {
      return;
    }
    void stream.send({
      question: pendingRef.current,
      sessionId: stream.sessionId ?? sessionId,
      mode: preferences.mode,
      language: preferences.language,
      model: preferences.model || undefined,
    });
  };

  const activeMode = meta?.modes.find((mode) => mode.code === preferences.mode);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Hỏi đáp tài liệu"
        description="Đặt câu hỏi về AWS SAA-C03. Câu trả lời dựa trên kho tài liệu và kèm trích dẫn tới đúng trang."
        actions={
          <Button variant="secondary" size="sm" onClick={startNewChat} disabled={busy}>
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" className="size-4">
              <path
                d="M10 4.5v11M4.5 10h11"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
              />
            </svg>
            Cuộc trò chuyện mới
          </Button>
        }
      />

      {metaError ? (
        <p className="text-xs text-muted">
          Không tải được tùy chọn hệ thống; đang dùng giá trị mặc định.
        </p>
      ) : null}

      <div className="flex flex-col gap-4">
        {loadingHistory ? (
          <div className="flex justify-center py-10">
            <Spinner label="Đang tải cuộc trò chuyện..." />
          </div>
        ) : null}

        {historyError ? (
          <ErrorState
            message={historyError}
            onRetry={() => {
              if (!sessionId) {
                startNewChat();
                return;
              }
              setLoadingHistory(true);
              setHistoryError(null);
              setHistoryKey((value) => value + 1);
            }}
          />
        ) : null}

        {!loadingHistory && !historyError && entries.length === 0 && !pendingQuestion ? (
          <Card className="border-brand-100 bg-gradient-to-br from-white to-brand-50">
            <h2 className="text-lg font-semibold text-brand-900">
              Bắt đầu bằng một câu hỏi về kiến trúc AWS
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Bạn có thể hỏi khái niệm, so sánh dịch vụ hoặc nhờ phân tích một tình huống thiết
              kế. Chế độ “Giải thích từng bước” phù hợp với câu hỏi vận dụng (K3).
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => submit(suggestion)}
                  className="rounded-lg border border-brand-100 bg-white px-4 py-3 text-left text-sm text-brand-800 transition-colors hover:border-brand-400 hover:bg-brand-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </Card>
        ) : null}

        <MessageList entries={entries} />

        {pendingQuestion ? (
          <div className="flex flex-col gap-3">
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-700 px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
                {pendingQuestion}
              </div>
            </div>
            <div className="flex justify-start">
              <div className="w-full max-w-[92%] rounded-2xl rounded-bl-md border border-line bg-white px-4 py-3 shadow-sm sm:max-w-[85%]">
                {stream.status === "error" ? (
                  <div className="flex flex-col gap-3">
                    <p className="text-sm text-danger">
                      {stream.error?.message ?? "Không nhận được câu trả lời."}
                    </p>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={retry}>
                        Thử lại
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          pendingRef.current = null;
                          setPendingQuestion(null);
                          stream.reset();
                        }}
                      >
                        Bỏ qua
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-3">
                    {stream.answer ? (
                      <>
                        <Markdown>{stream.answer}</Markdown>
                        <span aria-hidden="true" className="streaming-caret" />
                      </>
                    ) : (
                      <p className="text-sm text-muted">
                        {stream.status === "reconnecting"
                          ? "Đang kết nối lại để tiếp tục câu trả lời..."
                          : "Đang tìm tài liệu và soạn câu trả lời..."}
                      </p>
                    )}
                    {stream.citations?.items?.length ? (
                      <CitationChips citations={stream.citations.items} />
                    ) : null}
                    <div className="flex items-center justify-between gap-2 border-t border-line pt-2">
                      <span className="text-xs text-muted">
                        {activeMode?.label ?? "Đang trả lời"}
                        {stream.meta?.summary_used ? " · Có dùng tóm tắt hội thoại" : ""}
                      </span>
                      <Button variant="secondary" size="sm" onClick={stream.cancel}>
                        <span aria-hidden="true" className="size-2.5 rounded-[2px] bg-danger" />
                        Dừng tạo câu trả lời
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}

        <div ref={bottomRef} aria-hidden="true" className="h-px" />
      </div>

      <div className="sticky bottom-20 z-10 lg:bottom-4">
        <Card className="border-brand-200 shadow-[0_8px_30px_rgba(23,36,47,0.08)]">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div
                role="group"
                aria-label="Chế độ trả lời"
                className="inline-flex rounded-lg bg-surface p-1 text-xs font-medium"
              >
                <button
                  type="button"
                  aria-pressed={preferences.mode === "fast"}
                  onClick={() => setMode("fast")}
                  disabled={busy}
                  className={cn(
                    "rounded-md px-3 py-1.5 transition-colors",
                    preferences.mode === "fast"
                      ? "bg-white text-brand-800 shadow-sm"
                      : "text-muted hover:text-brand-700",
                  )}
                >
                  Trả lời nhanh
                </button>
                <button
                  type="button"
                  aria-pressed={preferences.mode === "step_by_step"}
                  onClick={() => setMode("step_by_step")}
                  disabled={busy}
                  className={cn(
                    "rounded-md px-3 py-1.5 transition-colors",
                    preferences.mode === "step_by_step"
                      ? "bg-white text-brand-800 shadow-sm"
                      : "text-muted hover:text-brand-700",
                  )}
                >
                  Giải thích từng bước
                </button>
              </div>
              {preferences.language === "en" ? <Badge tone="muted">Trả lời bằng English</Badge> : null}
            </div>

            <div>
              <label htmlFor="question" className="sr-only">
                Câu hỏi của bạn
              </label>
              <Textarea
                id="question"
                rows={2}
                value={composer}
                maxLength={maxChars}
                onChange={(event) => setComposer(event.target.value)}
                onKeyDown={onComposerKeyDown}
                placeholder="Nhập câu hỏi của bạn, ví dụ: Khi nào nên dùng Aurora Serverless v2?"
                aria-describedby="composer-help"
              />
              <div
                id="composer-help"
                className="mt-1.5 flex items-center justify-between gap-2 text-xs text-muted"
              >
                <span>Enter để gửi · Shift + Enter để xuống dòng</span>
                <span>{composer.length > maxChars * 0.8 ? `${composer.length}/${maxChars}` : ""}</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              {busy ? (
                <Button variant="secondary" onClick={stream.cancel}>
                  Dừng tạo câu trả lời
                </Button>
              ) : null}
              <Button
                onClick={() => submit(composer)}
                disabled={busy || composer.trim().length === 0}
              >
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" className="size-4">
                  <path
                    d="M3.5 10 16.5 4l-4 12-2.6-4.4L3.5 10z"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinejoin="round"
                  />
                </svg>
                Gửi câu hỏi
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function MessageList({ entries }: { entries: Entry[] }) {
  if (entries.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-3">
      {entries.map((entry) =>
        entry.role === "user" ? (
          <div key={entry.key} className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-700 px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
              {entry.content}
            </div>
          </div>
        ) : (
          <div key={entry.key} className="flex justify-start">
            <div className="w-full max-w-[92%] rounded-2xl rounded-bl-md border border-line bg-white px-4 py-3 shadow-sm sm:max-w-[85%]">
              {entry.content ? (
                <Markdown>{entry.content}</Markdown>
              ) : (
                <p className="text-sm italic text-muted">
                  Bạn đã dừng trước khi có câu trả lời.
                </p>
              )}
              {entry.aborted ? (
                <p className="mt-2 text-xs font-medium text-accent">
                  Câu trả lời đã bị dừng giữa chừng.
                </p>
              ) : null}
              {entry.citations.length ? (
                <div className="mt-3 border-t border-line pt-3">
                  <CitationChips citations={entry.citations} />
                </div>
              ) : null}
            </div>
          </div>
        ),
      )}
    </div>
  );
}

function ChatRoute() {
  const searchParams = useSearchParams();
  const initialSessionId = searchParams.get("session");
  return <ChatView key={initialSessionId ?? "new"} initialSessionId={initialSessionId} />;
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-20">
          <Spinner label="Đang tải trang hỏi đáp..." />
        </div>
      }
    >
      <ChatRoute />
    </Suspense>
  );
}
