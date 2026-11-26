"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { Button, Input, Label } from "@/components/ui";
import { createBrowserSupabase } from "@/lib/supabase/client";

type Mode = "signin" | "signup";

function translateAuthError(message: string): string {
  const lower = message.toLowerCase();
  if (lower.includes("invalid login credentials")) {
    return "Email hoặc mật khẩu không đúng. Bạn kiểm tra lại giúp nhé.";
  }
  if (lower.includes("email not confirmed")) {
    return "Email chưa được xác nhận. Hãy mở hộp thư và bấm liên kết xác nhận trước khi đăng nhập.";
  }
  if (lower.includes("user already registered")) {
    return "Email này đã có tài khoản. Hãy chuyển sang đăng nhập.";
  }
  if (lower.includes("password should be at least")) {
    return "Mật khẩu cần tối thiểu 6 ký tự.";
  }
  if (lower.includes("rate limit") || lower.includes("too many")) {
    return "Bạn thử quá nhiều lần. Vui lòng đợi một lát rồi thử lại.";
  }
  if (lower.includes("unable to validate email") || lower.includes("invalid email")) {
    return "Địa chỉ email không hợp lệ.";
  }
  return "Không đăng nhập được. Vui lòng thử lại.";
}

function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) {
    return "/chat";
  }
  return raw;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const nextPath = safeNext(searchParams.get("next"));

  const switchMode = (nextMode: Mode) => {
    setMode(nextMode);
    setError(null);
    setNotice(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) {
      return;
    }
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Bạn nhập email để tiếp tục.");
      return;
    }
    if (password.length < 6) {
      setError("Mật khẩu cần tối thiểu 6 ký tự.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    const supabase = createBrowserSupabase();
    try {
      if (mode === "signin") {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: trimmedEmail,
          password,
        });
        if (signInError) {
          setError(translateAuthError(signInError.message));
          return;
        }
        router.replace(nextPath);
        router.refresh();
      } else {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: trimmedEmail,
          password,
        });
        if (signUpError) {
          setError(translateAuthError(signUpError.message));
          return;
        }
        if (data.session) {
          router.replace(nextPath);
          router.refresh();
          return;
        }
        setNotice(
          "Tài khoản đã được tạo. Hãy mở hộp thư để xác nhận email, sau đó quay lại đăng nhập.",
        );
        setMode("signin");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-brand-900 p-10 text-white lg:flex">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-brand-700/60 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-brand-500/30 blur-3xl"
        />
        <div className="relative">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-brand-950 shadow-2xl">
            <Image
              src="/logo.png"
              alt="Logo AWS RAG SAA-C03"
              width={1024}
              height={683}
              sizes="(min-width: 1024px) 50vw, 192px"
              priority
              className="h-auto w-full"
            />
          </div>
          <h1 className="mt-8 max-w-lg text-3xl font-semibold leading-tight tracking-tight">
            Ôn thi AWS SAA-C03 có căn cứ, từng bước một.
          </h1>
          <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-100">
            Hỏi đáp dựa trên tài liệu gốc, trích dẫn tới đúng trang, luyện đề theo bốn lĩnh
            vực của blueprint và theo dõi tiến bộ của bạn.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-brand-50">
            <li className="flex items-start gap-3">
              <CheckBullet />
              Câu trả lời kèm trích dẫn bấm được tới tài liệu và số trang.
            </li>
            <li className="flex items-start gap-3">
              <CheckBullet />
              Hai chế độ: trả lời nhanh hoặc giải thích từng bước có kiểm chứng.
            </li>
            <li className="flex items-start gap-3">
              <CheckBullet />
              Luyện đề theo lĩnh vực, chấm điểm ngay và lưu lịch sử làm bài.
            </li>
          </ul>
        </div>
        <p className="relative text-xs text-brand-200">
          Đồ án tốt nghiệp · Chatbot RAG luyện thi AWS SAA-C03
        </p>
      </section>

      <section className="flex items-center justify-center bg-surface px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <div className="mx-auto w-48 overflow-hidden rounded-xl bg-brand-950">
              <Image
                src="/logo.png"
                alt="Logo AWS RAG SAA-C03"
                width={1024}
                height={683}
                sizes="(min-width: 1024px) 50vw, 192px"
                priority
                className="h-auto w-full"
              />
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-white p-6 shadow-sm sm:p-8">
            <h2 className="text-xl font-semibold tracking-tight text-brand-900">
              {mode === "signin" ? "Đăng nhập để tiếp tục" : "Tạo tài khoản học tập"}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {mode === "signin"
                ? "Dùng email và mật khẩu của bạn. Phiên đăng nhập được lưu bằng cookie bảo mật."
                : "Chỉ cần email và mật khẩu tối thiểu 6 ký tự."}
            </p>

            <div
              role="tablist"
              aria-label="Chọn hình thức đăng nhập"
              className="mt-5 grid grid-cols-2 gap-1 rounded-lg bg-surface p-1 text-sm"
            >
              <button
                role="tab"
                aria-selected={mode === "signin"}
                type="button"
                onClick={() => switchMode("signin")}
                className={`rounded-md px-3 py-2 font-medium transition-colors ${
                  mode === "signin"
                    ? "bg-white text-brand-800 shadow-sm"
                    : "text-muted hover:text-brand-700"
                }`}
              >
                Đăng nhập
              </button>
              <button
                role="tab"
                aria-selected={mode === "signup"}
                type="button"
                onClick={() => switchMode("signup")}
                className={`rounded-md px-3 py-2 font-medium transition-colors ${
                  mode === "signup"
                    ? "bg-white text-brand-800 shadow-sm"
                    : "text-muted hover:text-brand-700"
                }`}
              >
                Đăng ký
              </button>
            </div>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4" noValidate>
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  placeholder="ban@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="password">Mật khẩu</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={mode === "signin" ? "current-password" : "new-password"}
                    placeholder="Tối thiểu 6 ký tự"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="pr-20"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-brand-700 hover:text-brand-900"
                    aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  >
                    {showPassword ? "Ẩn" : "Hiện"}
                  </button>
                </div>
              </div>

              {error ? (
                <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              ) : null}
              {notice ? (
                <p
                  role="status"
                  className="rounded-lg bg-success-soft px-3 py-2 text-sm text-success"
                >
                  {notice}
                </p>
              ) : null}

              <Button type="submit" className="w-full" disabled={busy}>
                {busy
                  ? "Đang xử lý..."
                  : mode === "signin"
                    ? "Đăng nhập"
                    : "Tạo tài khoản"}
              </Button>
            </form>
          </div>
          <p className="mt-4 text-center text-xs text-muted">
            Bằng việc tiếp tục, bạn đồng ý dùng tài khoản cho mục đích học tập của đồ án.
          </p>
        </div>
      </section>
    </main>
  );
}

function CheckBullet() {
  return (
    <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-white/15">
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" className="size-3.5">
        <path
          d="m5 10.5 3 3 7-7"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center bg-surface text-sm text-muted">
          Đang tải trang đăng nhập...
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
