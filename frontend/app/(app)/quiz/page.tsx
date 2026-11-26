"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Markdown } from "@/components/Markdown";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Label,
  PageHeader,
  Select,
  Spinner,
  cn,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import type {
  QuizAttempt,
  QuizAttemptList,
  QuizDomains,
  QuizQuestion,
  QuizSubmitResult,
} from "@/lib/types";

type Stage = "setup" | "taking" | "result";

const COUNT_OPTIONS = [5, 10, 15, 20];
const ALL_DOMAIN = "all";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

export default function QuizPage() {
  const [stage, setStage] = useState<Stage>("setup");
  const [domains, setDomains] = useState<QuizDomains | null>(null);
  const [domainsError, setDomainsError] = useState<string | null>(null);
  const [loadingDomains, setLoadingDomains] = useState(true);
  const [domain, setDomain] = useState<string>(ALL_DOMAIN);
  const [count, setCount] = useState(5);

  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [questionsError, setQuestionsError] = useState<string | null>(null);

  const [result, setResult] = useState<QuizSubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [attempts, setAttempts] = useState<QuizAttempt[]>([]);
  const [attemptsTotal, setAttemptsTotal] = useState(0);
  const [attemptsError, setAttemptsError] = useState<string | null>(null);
  const [loadingAttempts, setLoadingAttempts] = useState(true);
  const [attemptsLoaded, setAttemptsLoaded] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let ignore = false;
    apiRequest<QuizDomains>("/quiz/domains")
      .then((data) => {
        if (ignore) {
          return;
        }
        setDomains(data);
        setDomainsError(null);
      })
      .catch((caught: unknown) => {
        if (ignore) {
          return;
        }
        setDomainsError(caught instanceof Error ? caught.message : "Không tải được lĩnh vực.");
      })
      .finally(() => {
        if (!ignore) {
          setLoadingDomains(false);
        }
      });
    apiRequest<QuizAttemptList>("/quiz/attempts?limit=10")
      .then((data) => {
        if (ignore) {
          return;
        }
        setAttempts(data.items);
        setAttemptsTotal(data.total);
        setAttemptsError(null);
        setAttemptsLoaded(true);
      })
      .catch((caught: unknown) => {
        if (ignore) {
          return;
        }
        setAttemptsError(
          caught instanceof Error ? caught.message : "Không tải được lịch sử làm bài.",
        );
      })
      .finally(() => {
        if (!ignore) {
          setLoadingAttempts(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (stage !== "taking") {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }
    timerRef.current = setInterval(() => {
      if (startedAtRef.current) {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }
    }, 1000);
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [stage]);

  const startQuiz = async () => {
    setLoadingQuestions(true);
    setQuestionsError(null);
    setSubmitError(null);
    try {
      const data = await apiRequest<{ items: QuizQuestion[] }>("/quiz/questions", {
        method: "POST",
        body: {
          domain: domain === ALL_DOMAIN ? null : domain,
          count,
        },
      });
      if (data.items.length === 0) {
        setQuestionsError("Kho câu hỏi chưa có câu phù hợp. Hãy chọn lĩnh vực khác.");
        return;
      }
      setQuestions(data.items);
      setAnswers({});
      setResult(null);
      startedAtRef.current = Date.now();
      setElapsed(0);
      setStage("taking");
      window.scrollTo({ top: 0 });
    } catch (caught) {
      setQuestionsError(caught instanceof Error ? caught.message : "Không tạo được đề.");
    } finally {
      setLoadingQuestions(false);
    }
  };

  const answeredCount = useMemo(
    () => questions.filter((question) => Boolean(answers[question.id])).length,
    [questions, answers],
  );
  const unanswered = questions.length - answeredCount;

  const submitQuiz = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const durationSeconds = startedAtRef.current
        ? Math.round((Date.now() - startedAtRef.current) / 1000)
        : 0;
      const data = await apiRequest<QuizSubmitResult>("/quiz/submit", {
        method: "POST",
        body: {
          answers: questions.map((question) => ({
            question_id: question.id,
            selected: answers[question.id] ?? null,
          })),
          domain: domain === ALL_DOMAIN ? null : domain,
          duration_seconds: durationSeconds,
        },
      });
      setResult(data);
      setConfirmOpen(false);
      setStage("result");
      window.scrollTo({ top: 0 });
      setLoadingAttempts(true);
      setReloadKey((value) => value + 1);
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : "Không nộp được bài.");
    } finally {
      setSubmitting(false);
    }
  };

  const domainLabel = (code: string | null) => {
    if (!code) {
      return "Tổng hợp";
    }
    return domains?.items.find((item) => item.code === code)?.label ?? code;
  };

  const availableCount = useMemo(() => {
    if (!domains) {
      return 0;
    }
    if (domain === ALL_DOMAIN) {
      return domains.total;
    }
    return domains.items.find((item) => item.code === domain)?.count ?? 0;
  }, [domains, domain]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Luyện đề"
        description="Chọn lĩnh vực và số câu. Đáp án được xáo trộn phía máy chủ, bài làm được chấm ngay và lưu vào lịch sử."
        actions={
          stage !== "setup" ? (
            <Button variant="secondary" size="sm" onClick={() => setStage("setup")}>
              Về màn hình chọn đề
            </Button>
          ) : null
        }
      />

      {stage === "setup" ? (
        <Card>
          <h2 className="text-base font-semibold text-brand-900">Tạo lượt luyện tập</h2>
          {loadingDomains ? (
            <div className="mt-4">
              <Spinner label="Đang tải lĩnh vực..." />
            </div>
          ) : domainsError ? (
            <div className="mt-4">
              <ErrorState
                message={domainsError}
                onRetry={() => {
                  setLoadingDomains(true);
                  setDomainsError(null);
                  setReloadKey((value) => value + 1);
                }}
              />
            </div>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="domain">Lĩnh vực</Label>
                <Select
                  id="domain"
                  value={domain}
                  onChange={(event) => setDomain(event.target.value)}
                >
                  <option value={ALL_DOMAIN}>
                    Tất cả lĩnh vực ({domains?.total ?? 0} câu)
                  </option>
                  {domains?.items.map((item) => (
                    <option key={item.code} value={item.code}>
                      {item.label} ({item.count} câu)
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="count">Số câu</Label>
                <Select
                  id="count"
                  value={count}
                  onChange={(event) => setCount(Number(event.target.value))}
                >
                  {COUNT_OPTIONS.map((option) => (
                    <option key={option} value={option} disabled={option > availableCount}>
                      {option} câu{option > availableCount ? " (không đủ câu)" : ""}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          )}

          {questionsError ? (
            <div className="mt-4">
              <ErrorState message={questionsError} />
            </div>
          ) : null}

          <div className="mt-5 flex flex-col gap-3 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted">
              Kho hiện có <strong className="text-brand-900">{availableCount}</strong> câu phù hợp
              với lựa chọn.
            </p>
            <Button onClick={startQuiz} disabled={loadingQuestions || loadingDomains || !domains}>
              {loadingQuestions ? "Đang tạo đề..." : "Bắt đầu làm bài"}
            </Button>
          </div>
        </Card>
      ) : null}

      {stage === "taking" ? (
        <div className="flex flex-col gap-4">
          <Card className="flex flex-wrap items-center justify-between gap-3 border-brand-200">
            <div>
              <p className="text-sm font-medium text-brand-900">
                {domain === ALL_DOMAIN ? "Tất cả lĩnh vực" : domainLabel(domain)} ·{" "}
                {questions.length} câu
              </p>
              <p className="mt-0.5 text-xs text-muted">
                Đã trả lời {answeredCount}/{questions.length} · Thời gian{" "}
                {formatDuration(elapsed)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="h-2 w-32 overflow-hidden rounded-full bg-surface"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={questions.length}
                aria-valuenow={answeredCount}
                aria-label="Tiến độ trả lời"
              >
                <div
                  className="h-full rounded-full bg-brand-600 transition-[width]"
                  style={{
                    width: `${questions.length ? (answeredCount / questions.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <Button size="sm" onClick={() => setConfirmOpen(true)} disabled={submitting}>
                Nộp bài
              </Button>
            </div>
          </Card>

          {submitError ? <ErrorState message={submitError} /> : null}

          <ol className="flex flex-col gap-4">
            {questions.map((question, index) => (
              <li key={question.id}>
                <Card>
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold leading-relaxed text-brand-900">
                      <span className="mr-2 inline-flex size-6 items-center justify-center rounded-full bg-brand-700 text-xs text-white">
                        {index + 1}
                      </span>
                      <span className="whitespace-pre-wrap">{question.question}</span>
                    </p>
                    {question.domain ? (
                      <Badge tone="muted" className="shrink-0">
                        {domainLabel(question.domain)}
                      </Badge>
                    ) : null}
                  </div>
                  <fieldset className="mt-3">
                    <legend className="sr-only">Chọn đáp án cho câu {index + 1}</legend>
                    <div className="flex flex-col gap-2">
                      {question.options.map((option) => {
                        const selected = answers[question.id] === option.label;
                        return (
                          <label
                            key={option.label}
                            className={cn(
                              "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors",
                              selected
                                ? "border-brand-500 bg-brand-50 text-brand-900"
                                : "border-line bg-white hover:border-brand-200 hover:bg-surface",
                            )}
                          >
                            <input
                              type="radio"
                              name={`q-${question.id}`}
                              value={option.label}
                              checked={selected}
                              onChange={() =>
                                setAnswers((previous) => ({
                                  ...previous,
                                  [question.id]: option.label,
                                }))
                              }
                              className="mt-0.5 size-4 accent-[#1F4E79]"
                            />
                            <span className="whitespace-pre-wrap">
                              <span className="mr-2 font-semibold">{option.label}.</span>
                              {option.text}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                </Card>
              </li>
            ))}
          </ol>

          <div className="flex flex-col items-center gap-2 rounded-xl border border-line bg-white px-4 py-4">
            <p className="text-sm text-muted">
              {unanswered > 0
                ? `Còn ${unanswered} câu chưa trả lời. Bạn vẫn có thể nộp bài.`
                : "Bạn đã trả lời đủ các câu. Sẵn sàng nộp bài."}
            </p>
            <Button onClick={() => setConfirmOpen(true)} disabled={submitting}>
              Nộp bài và xem đáp án
            </Button>
          </div>
        </div>
      ) : null}

      {stage === "result" && result ? (
        <div className="flex flex-col gap-4">
          <Card className="border-brand-200 bg-gradient-to-br from-white to-brand-50">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-muted">Kết quả lượt làm bài</p>
                <p className="mt-1 text-3xl font-semibold text-brand-900">
                  {result.correct}/{result.total} câu đúng
                </p>
                <p className="mt-1 text-sm text-muted">
                  Điểm {Math.round(result.score * 100)}% ·{" "}
                  {domainLabel(result.domain)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={startQuiz} disabled={loadingQuestions}>
                  Làm lượt mới
                </Button>
                <Button onClick={() => setStage("setup")}>Chọn đề khác</Button>
              </div>
            </div>
          </Card>

          <ol className="flex flex-col gap-3">
            {result.items.map((item, index) => {
              const sourceQuestion = questions.find(
                (question) => question.id === item.question_id,
              );
              const selectedText = sourceQuestion?.options.find(
                (option) => option.label === item.selected,
              )?.text;
              const correctText = sourceQuestion?.options.find(
                (option) => option.label === item.correct_answer,
              )?.text;
              return (
                <li key={item.question_id}>
                  <Card
                    className={cn(
                      "border-l-4",
                      item.is_correct ? "border-l-success" : "border-l-danger",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold leading-relaxed text-brand-900">
                        <span className="mr-2">{index + 1}.</span>
                        <span className="whitespace-pre-wrap">{item.question}</span>
                      </p>
                      <Badge tone={item.is_correct ? "success" : "danger"} className="shrink-0">
                        {item.is_correct ? "Đúng" : "Sai"}
                      </Badge>
                    </div>
                    <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                      <div className="rounded-lg bg-surface px-3 py-2">
                        <dt className="text-xs text-muted">Bạn chọn</dt>
                        <dd className="mt-0.5 font-medium text-ink">
                          {item.selected
                            ? `${item.selected}. ${selectedText ?? ""}`
                            : "Chưa trả lời"}
                        </dd>
                      </div>
                      <div className="rounded-lg bg-success-soft px-3 py-2">
                        <dt className="text-xs text-success">Đáp án đúng</dt>
                        <dd className="mt-0.5 font-medium text-success">
                          {item.correct_answer}. {correctText ?? ""}
                        </dd>
                      </div>
                    </dl>
                    {item.explanation ? (
                      <div className="mt-3 rounded-lg border border-brand-100 bg-brand-50/60 px-3 py-2.5">
                        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-700">
                          Giải thích
                        </p>
                        <Markdown>{item.explanation}</Markdown>
                      </div>
                    ) : null}
                    {item.source ? (
                      <p className="mt-2 text-xs text-muted">Nguồn: {item.source}</p>
                    ) : null}
                  </Card>
                </li>
              );
            })}
          </ol>
        </div>
      ) : null}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-brand-900">Lịch sử làm bài gần đây</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setLoadingAttempts(true);
              setAttemptsError(null);
              setReloadKey((value) => value + 1);
            }}
            disabled={loadingAttempts}
          >
            Làm mới
          </Button>
        </div>
        {loadingAttempts && !attemptsLoaded ? (
          <div className="mt-3">
            <Spinner label="Đang tải lịch sử..." />
          </div>
        ) : attemptsError ? (
          <div className="mt-3">
            <ErrorState
              message={attemptsError}
              onRetry={() => {
                setLoadingAttempts(true);
                setAttemptsError(null);
                setReloadKey((value) => value + 1);
              }}
            />
          </div>
        ) : attempts.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              title="Chưa có lượt làm bài nào"
              description="Kết quả mỗi lượt luyện tập sẽ được lưu tự động vào đây để bạn theo dõi tiến bộ."
            />
          </div>
        ) : (
          <>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                    <th className="py-2 pr-3 font-medium">Thời điểm</th>
                    <th className="py-2 pr-3 font-medium">Lĩnh vực</th>
                    <th className="py-2 pr-3 font-medium">Kết quả</th>
                    <th className="py-2 font-medium">Điểm</th>
                  </tr>
                </thead>
                <tbody>
                  {attempts.map((attempt) => (
                    <tr key={attempt.id} className="border-b border-line last:border-0">
                      <td className="py-2 pr-3 text-muted">{formatDate(attempt.created_at)}</td>
                      <td className="py-2 pr-3">{domainLabel(attempt.domain)}</td>
                      <td className="py-2 pr-3">
                        {attempt.correct}/{attempt.total}
                      </td>
                      <td className="py-2">
                        <span
                          className={cn(
                            "font-medium",
                            attempt.score >= 0.7 ? "text-success" : "text-danger",
                          )}
                        >
                          {Math.round(attempt.score * 100)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-muted">
              Hiển thị {attempts.length}/{attemptsTotal} lượt gần nhất.
            </p>
          </>
        )}
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        title="Nộp bài?"
        description={
          unanswered > 0
            ? `Bạn còn ${unanswered} câu chưa trả lời. Các câu bỏ trống sẽ được tính là sai. Vẫn nộp bài?`
            : "Bài làm sẽ được chấm ngay và lưu vào lịch sử. Tiếp tục nộp?"
        }
        confirmLabel="Nộp bài"
        busy={submitting}
        onConfirm={submitQuiz}
        onClose={() => setConfirmOpen(false)}
      />
    </div>
  );
}
