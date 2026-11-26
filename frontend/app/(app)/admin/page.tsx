"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import type { AdminStats } from "@/lib/types";

const PERIODS = [7, 30, 90];

function formatNumber(value: number): string {
  return new Intl.NumberFormat("vi-VN").format(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
}

function formatMs(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${formatNumber(Math.round(value))} ms`;
}

function formatUsd(value: number): string {
  return `$${value.toLocaleString("vi-VN", { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short" }).format(new Date(value));
}

export default function AdminPage() {
  const { ready, profile, isAdmin, refreshProfile } = useAuth();
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const refresh = () => {
    setLoading(true);
    setError(null);
    setForbidden(false);
    setReloadKey((value) => value + 1);
  };

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    let ignore = false;
    apiRequest<AdminStats>(`/admin/stats?days=${days}`)
      .then((data) => {
        if (ignore) {
          return;
        }
        setStats(data);
        setError(null);
        setForbidden(false);
      })
      .catch((caught: unknown) => {
        if (ignore) {
          return;
        }
        const code =
          typeof caught === "object" && caught !== null && "code" in caught
            ? String((caught as { code: unknown }).code)
            : "";
        if (code === "admin_required") {
          setForbidden(true);
          return;
        }
        setError(caught instanceof Error ? caught.message : "Không tải được thống kê.");
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [isAdmin, days, reloadKey]);

  if (!ready) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Đang kiểm tra quyền truy cập..." />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title="Quản trị" />
        <ErrorState
          message="Không tải được thông tin tài khoản để kiểm tra quyền quản trị."
          onRetry={() => void refreshProfile()}
        />
      </div>
    );
  }

  if (!isAdmin || forbidden) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title="Quản trị" description="Khu vực dành cho quản trị viên." />
        <Card>
          <div className="flex flex-col items-start gap-3">
            <Badge tone="danger">Không có quyền truy cập</Badge>
            <p className="text-sm text-muted">
              Tài khoản <strong className="text-brand-900">{profile.email}</strong> không nằm
              trong danh sách quản trị viên. Nếu bạn cần quyền này, hãy liên hệ người phụ trách
              đồ án để bổ sung email vào biến môi trường <code>ADMIN_EMAILS</code>.
            </p>
            <Link
              href="/chat"
              className="inline-flex min-h-10 items-center rounded-lg bg-brand-700 px-4 text-sm font-medium text-white hover:bg-brand-600"
            >
              Về trang hỏi đáp
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Trang quản trị"
        description="Thống kê kho tri thức và hoạt động của chatbot trong khoảng thời gian đã chọn."
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="period" className="text-sm text-muted">
              Khoảng thời gian
            </label>
            <Select
              id="period"
              value={days}
              onChange={(event) => {
                setDays(Number(event.target.value));
                setLoading(true);
                setError(null);
                setForbidden(false);
              }}
              className="w-36"
            >
              {PERIODS.map((period) => (
                <option key={period} value={period}>
                  {period} ngày
                </option>
              ))}
            </Select>
            <Button variant="secondary" size="sm" onClick={refresh} disabled={loading}>
              Làm mới
            </Button>
          </div>
        }
      />

      {loading && !stats ? (
        <div className="flex justify-center py-12">
          <Spinner label="Đang tải thống kê..." />
        </div>
      ) : null}

      {error ? <ErrorState message={error} onRetry={refresh} /> : null}

      {stats ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <KpiCard
              label="Câu hỏi trong kho"
              value={formatNumber(stats.totals.questions)}
              hint={`${formatNumber(stats.totals.documents)} tài liệu · ${formatNumber(
                stats.totals.chunks,
              )} chunk`}
            />
            <KpiCard
              label={`Lượt hỏi (${stats.period_days} ngày)`}
              value={formatNumber(stats.totals.queries)}
              hint={`${formatNumber(stats.totals.sessions)} phiên hội thoại`}
            />
            <KpiCard
              label="Chi phí ước tính"
              value={formatUsd(stats.totals.cost_usd)}
              hint="Theo bảng giá trong config/generation.yaml"
            />
            <KpiCard
              label="Tỷ lệ từ chối"
              value={formatPercent(stats.totals.refusal_rate)}
              hint={`Tỷ lệ lỗi ${formatPercent(stats.totals.error_rate)}`}
              tone={stats.totals.refusal_rate > 0.2 ? "warn" : "normal"}
            />
            <KpiCard
              label="Độ trễ phản hồi p95"
              value={formatMs(stats.totals.latency_p95_ms)}
              hint={`Trung vị p50: ${formatMs(stats.totals.latency_p50_ms)}`}
            />
            <KpiCard
              label="TTFT p95"
              value={formatMs(stats.totals.ttft_p95_ms)}
              hint="Thời gian tới token đầu tiên"
            />
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-brand-900">Hoạt động theo ngày</h2>
              <span className="text-xs text-muted">
                Tạo lúc {new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(stats.generated_at))}
              </span>
            </div>
            {stats.daily.length === 0 ? (
              <div className="mt-3">
                <EmptyState
                  title="Chưa có lượt hỏi nào trong kỳ"
                  description="Số liệu sẽ xuất hiện sau khi người dùng đặt câu hỏi qua chatbot."
                />
              </div>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                      <th className="py-2 pr-3 font-medium">Ngày</th>
                      <th className="py-2 pr-3 font-medium">Lượt hỏi</th>
                      <th className="py-2 pr-3 font-medium">Từ chối</th>
                      <th className="py-2 pr-3 font-medium">Chi phí</th>
                      <th className="py-2 font-medium">Độ trễ p95</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.daily.map((point) => (
                      <tr key={point.day} className="border-b border-line last:border-0">
                        <td className="py-2 pr-3 font-medium text-brand-900">
                          {formatDate(point.day)}
                        </td>
                        <td className="py-2 pr-3">{formatNumber(point.queries)}</td>
                        <td className="py-2 pr-3">{formatNumber(point.refusals)}</td>
                        <td className="py-2 pr-3">{formatUsd(point.cost_usd)}</td>
                        <td className="py-2">{formatMs(point.latency_p95_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <p className="text-xs text-muted">
            Chi phí chỉ là ước tính từ số token và bảng giá cấu hình; nếu bảng giá để 0 thì giá trị
            hiển thị là $0. Dữ liệu lấy từ bảng <code>query_logs</code> của backend.
          </p>
        </>
      ) : null}
    </div>
  );
}

function KpiCard({
  label,
  value,
  hint,
  tone = "normal",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "normal" | "warn";
}) {
  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p
        className={`mt-1.5 text-2xl font-semibold tracking-tight ${
          tone === "warn" ? "text-danger" : "text-brand-900"
        }`}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}
