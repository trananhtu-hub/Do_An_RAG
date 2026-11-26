"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  Label,
  Modal,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import type { ChatSession, SessionList } from "@/lib/types";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function HistoryPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [query, setQuery] = useState("");

  const [renaming, setRenaming] = useState<ChatSession | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

  const [deleting, setDeleting] = useState<ChatSession | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    apiRequest<SessionList>("/sessions?limit=100")
      .then((data) => {
        if (ignore) {
          return;
        }
        setSessions(data.items);
        setTotal(data.total);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (ignore) {
          return;
        }
        setError(caught instanceof Error ? caught.message : "Không tải được lịch sử.");
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return sessions;
    }
    return sessions.filter((session) =>
      (session.title ?? "").toLowerCase().includes(needle),
    );
  }, [sessions, query]);

  const openRename = (session: ChatSession) => {
    setRenaming(session);
    setRenameValue(session.title ?? "");
    setRenameError(null);
  };

  const submitRename = async () => {
    if (!renaming) {
      return;
    }
    const title = renameValue.trim();
    if (!title) {
      setRenameError("Tiêu đề không được để trống.");
      return;
    }
    setRenameBusy(true);
    setRenameError(null);
    try {
      const updated = await apiRequest<ChatSession>(`/sessions/${renaming.id}`, {
        method: "PATCH",
        body: { title },
      });
      setSessions((previous) =>
        previous.map((session) => (session.id === updated.id ? updated : session)),
      );
      setRenaming(null);
      setNotice("Đã đổi tên cuộc trò chuyện.");
    } catch (caught) {
      setRenameError(caught instanceof Error ? caught.message : "Không đổi được tên.");
    } finally {
      setRenameBusy(false);
    }
  };

  const submitDelete = async () => {
    if (!deleting) {
      return;
    }
    setDeleteBusy(true);
    setActionError(null);
    try {
      await apiRequest<void>(`/sessions/${deleting.id}`, { method: "DELETE" });
      setSessions((previous) => previous.filter((session) => session.id !== deleting.id));
      setTotal((value) => Math.max(0, value - 1));
      setDeleting(null);
      setNotice("Đã xóa cuộc trò chuyện.");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Không xóa được phiên.");
      setDeleting(null);
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Lịch sử hội thoại"
        description="Tìm lại các câu hỏi đã trao đổi, đổi tên để dễ nhớ hoặc xóa những phiên không còn cần thiết."
        actions={
          <Link
            href="/chat"
            className="inline-flex min-h-9 items-center rounded-lg bg-brand-700 px-3 text-sm font-medium text-white hover:bg-brand-600"
          >
            Cuộc trò chuyện mới
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <label htmlFor="session-search" className="sr-only">
            Tìm theo tiêu đề cuộc trò chuyện
          </label>
          <div className="relative">
            <svg
              viewBox="0 0 20 20"
              fill="none"
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
            >
              <circle cx="9" cy="9" r="5.5" stroke="currentColor" strokeWidth="1.5" />
              <path d="m13.5 13.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <Input
              id="session-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm theo tiêu đề..."
              className="pl-9"
            />
          </div>
        </div>
        <p className="text-sm text-muted">
          {loading ? "Đang tải..." : `${filtered.length} phiên${query ? " khớp" : ""} / ${total} tổng`}
        </p>
      </div>

      {notice ? (
        <p role="status" className="rounded-lg bg-success-soft px-3 py-2 text-sm text-success">
          {notice}
        </p>
      ) : null}
      {actionError ? <ErrorState message={actionError} /> : null}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner label="Đang tải lịch sử hội thoại..." />
        </div>
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={() => {
            setLoading(true);
            setError(null);
            setReloadKey((value) => value + 1);
          }}
        />
      ) : sessions.length === 0 ? (
        <EmptyState
          title="Chưa có cuộc trò chuyện nào"
          description="Khi bạn đặt câu hỏi ở màn hình Hỏi đáp, phiên hội thoại sẽ xuất hiện tại đây."
          action={
            <Link
              href="/chat"
              className="inline-flex min-h-10 items-center rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-600"
            >
              Bắt đầu hỏi đáp
            </Link>
          }
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Không tìm thấy phiên phù hợp"
          description={`Không có tiêu đề nào chứa “${query.trim()}”. Thử từ khóa khác nhé.`}
          action={
            <Button variant="secondary" size="sm" onClick={() => setQuery("")}>
              Xóa từ khóa
            </Button>
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {filtered.map((session) => (
              <li key={session.id}>
                <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="truncate text-sm font-semibold text-brand-900">
                        {session.title?.trim() || "Cuộc trò chuyện không tiêu đề"}
                      </h2>
                      <Badge tone="muted">{session.message_count} tin nhắn</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      Cập nhật {formatDate(session.updated_at)} · {session.token_count} token
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Link
                      href={`/chat?session=${session.id}`}
                      className="inline-flex min-h-9 items-center rounded-lg border border-line bg-white px-3 text-sm font-medium text-brand-800 hover:border-brand-300 hover:bg-brand-50"
                    >
                      Mở
                    </Link>
                    <Button variant="secondary" size="sm" onClick={() => openRename(session)}>
                      Đổi tên
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeleting(session)}>
                      <span className="text-danger">Xóa</span>
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
          {total > sessions.length ? (
            <p className="text-xs text-muted">
              Đang hiển thị {sessions.length}/{total} phiên gần nhất.
            </p>
          ) : null}
        </>
      )}

      <Modal
        open={renaming !== null}
        title="Đổi tên cuộc trò chuyện"
        onClose={() => (renameBusy ? undefined : setRenaming(null))}
      >
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="rename-title">Tiêu đề mới</Label>
            <Input
              id="rename-title"
              value={renameValue}
              maxLength={200}
              onChange={(event) => setRenameValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void submitRename();
                }
              }}
            />
          </div>
          {renameError ? (
            <p role="alert" className="text-sm text-danger">
              {renameError}
            </p>
          ) : null}
          <div className="mt-1 flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setRenaming(null)}
              disabled={renameBusy}
            >
              Hủy
            </Button>
            <Button onClick={submitRename} disabled={renameBusy}>
              {renameBusy ? "Đang lưu..." : "Lưu tên mới"}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="Xóa cuộc trò chuyện?"
        description={`Phiên “${
          deleting?.title?.trim() || "không tiêu đề"
        }” cùng toàn bộ tin nhắn sẽ bị xóa vĩnh viễn. Thao tác này không thể hoàn tác.`}
        confirmLabel="Xóa vĩnh viễn"
        busy={deleteBusy}
        onConfirm={submitDelete}
        onClose={() => (deleteBusy ? undefined : setDeleting(null))}
      />
    </div>
  );
}
