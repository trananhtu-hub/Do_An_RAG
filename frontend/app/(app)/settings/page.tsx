"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  Label,
  PageHeader,
  Select,
  Spinner,
  cn,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import {
  clearPreferences,
  savePreferences,
  usePreferences,
} from "@/lib/preferences";
import type {
  AnswerLanguage,
  AnswerMode,
  AppMeta,
  Preferences,
} from "@/lib/types";

export default function SettingsPage() {
  const { user, profile, isAdmin, signOut } = useAuth();
  const router = useRouter();

  const [meta, setMeta] = useState<AppMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const preferences = usePreferences();
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadMeta = useCallback(() => {
    apiRequest<AppMeta>("/meta")
      .then((data) => {
        setMeta(data);
        setMetaError(null);
      })
      .catch((caught: unknown) =>
        setMetaError(caught instanceof Error ? caught.message : "Không tải được tùy chọn."),
      )
      .finally(() => setLoadingMeta(false));
  }, []);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const update = (patch: Partial<Preferences>) => {
    savePreferences({ ...preferences, ...patch });
    setSavedAt(new Date().toLocaleTimeString("vi-VN"));
  };

  const clearAllData = async () => {
    setClearing(true);
    setClearError(null);
    try {
      const sessions = await apiRequest<{ deleted: number }>("/sessions", {
        method: "DELETE",
      });
      const attempts = await apiRequest<{ deleted: number }>("/quiz/attempts", {
        method: "DELETE",
      });
      clearPreferences();
      setConfirmOpen(false);
      setNotice(
        `Đã xóa ${sessions.deleted} phiên hội thoại và ${attempts.deleted} lượt làm bài. Tùy chọn cá nhân đã được đặt lại.`,
      );
    } catch (caught) {
      setClearError(caught instanceof Error ? caught.message : "Không xóa được dữ liệu.");
    } finally {
      setClearing(false);
    }
  };

  const email = profile?.email ?? user?.email ?? "Chưa đăng nhập";
  const modeOptions = meta?.modes ?? [];
  const languageOptions = meta?.languages ?? [];
  const selectedModel = preferences.model || meta?.default_model || "";

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Cài đặt"
        description="Điều chỉnh cách chatbot trả lời và quản lý dữ liệu học tập của bạn."
      />

      {notice ? (
        <p role="status" className="rounded-lg bg-success-soft px-3 py-2 text-sm text-success">
          {notice}
        </p>
      ) : null}
      {clearError ? <ErrorState message={clearError} /> : null}

      <Card>
        <h2 className="text-base font-semibold text-brand-900">Tài khoản</h2>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-brand-900">{email}</p>
            <div className="mt-1 flex items-center gap-2">
              <Badge tone={isAdmin ? "accent" : "muted"}>
                {isAdmin ? "Quản trị viên" : "Học viên"}
              </Badge>
              <span className="text-xs text-muted">Đăng nhập bằng Supabase Auth</span>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await signOut();
              router.replace("/login");
              router.refresh();
            }}
          >
            Đăng xuất
          </Button>
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-brand-900">Cách trả lời</h2>
          {savedAt ? <span className="text-xs text-muted">Đã lưu lúc {savedAt}</span> : null}
        </div>

        {loadingMeta ? (
          <div className="mt-4">
            <Spinner label="Đang tải tùy chọn..." />
          </div>
        ) : metaError ? (
          <div className="mt-4">
            <ErrorState
              message={metaError}
              onRetry={() => {
                setLoadingMeta(true);
                setMetaError(null);
                loadMeta();
              }}
            />
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-5">
            <div>
              <Label htmlFor="model">Mô hình</Label>
              <Select
                id="model"
                value={selectedModel}
                onChange={(event) => update({ model: event.target.value })}
              >
                {meta?.models.map((model) => (
                  <option key={model.code} value={model.code}>
                    {model.label}
                  </option>
                ))}
              </Select>
              <p className="mt-1.5 text-xs text-muted">
                {meta?.models.find((model) => model.code === selectedModel)?.description ??
                  "Mô hình sinh câu trả lời đang được hệ thống hỗ trợ."}
              </p>
            </div>

            <fieldset>
              <legend className="mb-1.5 block text-sm font-medium text-brand-900">
                Chế độ trả lời
              </legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {modeOptions.map((mode) => {
                  const selected = preferences.mode === mode.code;
                  return (
                    <label
                      key={mode.code}
                      className={cn(
                        "flex cursor-pointer flex-col gap-1 rounded-xl border px-4 py-3 transition-colors",
                        selected
                          ? "border-brand-500 bg-brand-50"
                          : "border-line bg-white hover:border-brand-200",
                      )}
                    >
                      <span className="flex items-center gap-2 text-sm font-medium text-brand-900">
                        <input
                          type="radio"
                          name="answer-mode"
                          value={mode.code}
                          checked={selected}
                          onChange={() => update({ mode: mode.code as AnswerMode })}
                          className="size-4 accent-[#1F4E79]"
                        />
                        {mode.label}
                      </span>
                      {mode.description ? (
                        <span className="pl-6 text-xs leading-relaxed text-muted">
                          {mode.description}
                        </span>
                      ) : null}
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-1.5 block text-sm font-medium text-brand-900">
                Ngôn ngữ trả lời
              </legend>
              <div className="flex flex-wrap gap-2">
                {languageOptions.map((language) => {
                  const selected = preferences.language === language.code;
                  return (
                    <label
                      key={language.code}
                      className={cn(
                        "inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors",
                        selected
                          ? "border-brand-500 bg-brand-50 text-brand-900"
                          : "border-line bg-white text-muted hover:border-brand-200",
                      )}
                    >
                      <input
                        type="radio"
                        name="answer-language"
                        value={language.code}
                        checked={selected}
                        onChange={() => update({ language: language.code as AnswerLanguage })}
                        className="size-4 accent-[#1F4E79]"
                      />
                      {language.label}
                    </label>
                  );
                })}
              </div>
              <p className="mt-1.5 text-xs text-muted">
                Giao diện luôn hiển thị bằng tiếng Việt; tùy chọn này chỉ đổi ngôn ngữ của câu
                trả lời.
              </p>
            </fieldset>
          </div>
        )}
      </Card>

      <Card className="border-[#f0cccc]">
        <h2 className="text-base font-semibold text-danger">Vùng nguy hiểm</h2>
        <p className="mt-1 text-sm text-muted">
          Xóa toàn bộ phiên hội thoại, tin nhắn, lịch sử làm bài và tùy chọn cá nhân trên thiết bị
          này. Tài khoản đăng nhập vẫn được giữ.
        </p>
        <Button variant="danger" className="mt-3" onClick={() => setConfirmOpen(true)}>
          Xóa toàn bộ dữ liệu của tôi
        </Button>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        title="Xóa toàn bộ dữ liệu?"
        description="Toàn bộ cuộc trò chuyện, tin nhắn và lịch sử làm bài của bạn sẽ bị xóa vĩnh viễn. Thao tác này không thể hoàn tác."
        confirmLabel="Xóa vĩnh viễn"
        busy={clearing}
        onConfirm={clearAllData}
        onClose={() => (clearing ? undefined : setConfirmOpen(false))}
      />
    </div>
  );
}
