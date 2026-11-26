"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useAuth } from "@/components/AuthProvider";
import { cn } from "@/components/ui";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <path
        d="M4 5.5h16v10H9l-4.5 3.5v-3.5H4z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M8 9.5h8M8 12.5h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function QuizIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <path
        d="M7 4h10a1.5 1.5 0 0 1 1.5 1.5v14A1.5 1.5 0 0 1 17 21H7a1.5 1.5 0 0 1-1.5-1.5v-14A1.5 1.5 0 0 1 7 4z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="m8.5 11.5 2 2 4-4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M9 17h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 7.5V12l3 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <path
        d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M19 13.5v-3l-2-.6a7 7 0 0 0-.8-1.8l1-1.9-2.1-2.1-1.9 1a7 7 0 0 0-1.8-.8l-.6-2h-3l-.6 2a7 7 0 0 0-1.8.8l-1.9-1-2.1 2.1 1 1.9a7 7 0 0 0-.8 1.8l-2 .6v3l2 .6a7 7 0 0 0 .8 1.8l-1 1.9 2.1 2.1 1.9-1a7 7 0 0 0 1.8.8l.6 2h3l.6-2a7 7 0 0 0 1.8-.8l1.9 1 2.1-2.1-1-1.9a7 7 0 0 0 .8-1.8z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AdminIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

const NAV_ITEMS: NavItem[] = [
  { href: "/chat", label: "Hỏi đáp", icon: <ChatIcon /> },
  { href: "/quiz", label: "Luyện đề", icon: <QuizIcon /> },
  { href: "/history", label: "Lịch sử", icon: <HistoryIcon /> },
  { href: "/settings", label: "Cài đặt", icon: <SettingsIcon /> },
  { href: "/admin", label: "Quản trị", icon: <AdminIcon />, adminOnly: true },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, isAdmin } = useAuth();
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div className="min-h-dvh lg:pl-64">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-brand-800 focus:shadow-lg"
      >
        Bỏ qua điều hướng
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col bg-brand-800 lg:flex">
        <Link
          href="/chat"
          className="block overflow-hidden border-b border-white/10 px-4 py-4"
          aria-label="Trang hỏi đáp"
        >
          <span className="block h-24 overflow-hidden rounded-lg border border-white/10 bg-brand-950">
            <Image
              src="/logo.png"
              alt="Logo AWS RAG SAA-C03"
              width={1536}
              height={1024}
              priority
              className="h-full w-full object-cover object-center"
            />
          </span>
        </Link>
        <nav aria-label="Điều hướng chính" className="flex flex-1 flex-col gap-1 px-3 py-4">
          {items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-white/15 text-white"
                    : "text-brand-100 hover:bg-white/10 hover:text-white",
                )}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-white/10 px-4 py-4">
          <p className="truncate text-sm font-medium text-white" title={user?.email ?? ""}>
            {user?.email ?? "Khách"}
          </p>
          <p className="mt-0.5 text-xs text-brand-200">
            {isAdmin ? "Quản trị viên" : "Học viên"}
          </p>
          <SignOutButton className="mt-3 w-full justify-start rounded-lg border border-white/20 px-3 py-2 text-sm text-brand-100 hover:bg-white/10 hover:text-white">
            Đăng xuất
          </SignOutButton>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-line bg-white/95 backdrop-blur">
        <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
          <Link
            href="/chat"
            className="flex items-center gap-2 lg:hidden"
            aria-label="AWS SAA-C03 – Trang hỏi đáp"
          >
            <span className="block h-9 w-14 overflow-hidden rounded-md bg-brand-950">
              <Image
                src="/logo.png"
                alt="Logo AWS RAG SAA-C03"
                width={1536}
                height={1024}
                priority
                className="h-full w-full object-cover object-center"
              />
            </span>
            <span className="text-sm font-semibold text-brand-900">AWS SAA-C03</span>
          </Link>
          <p className="hidden text-sm text-muted lg:block">
            Chatbot RAG luyện thi AWS Certified Solutions Architect – Associate
          </p>
          <AccountMenu />
        </div>
      </header>

      <main id="main-content" className="mx-auto w-full max-w-6xl px-4 pb-24 pt-6 sm:px-6 lg:pb-12">
        {children}
      </main>

      <nav
        aria-label="Điều hướng di động"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 backdrop-blur lg:hidden"
      >
        <ul className="mx-auto flex max-w-md items-stretch justify-around">
          {items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <li key={item.href} className="flex-1">
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium",
                    active ? "text-brand-700" : "text-muted hover:text-brand-700",
                  )}
                >
                  {item.icon}
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}

function SignOutButton({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const { signOut } = useAuth();
  const router = useRouter();
  return (
    <button
      type="button"
      className={className}
      onClick={async () => {
        await signOut();
        router.replace("/login");
        router.refresh();
      }}
    >
      {children}
    </button>
  );
}

function AccountMenu() {
  const { user, profile, isAdmin, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const email = profile?.email ?? user?.email ?? "Khách";
  const initial = email.slice(0, 1).toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-full border border-line bg-white py-1 pl-1 pr-2.5 text-left transition-colors hover:border-brand-300"
        title={`Đang đăng nhập với ${email}`}
      >
        <span className="flex size-8 items-center justify-center rounded-full bg-brand-700 text-sm font-semibold text-white">
          {initial}
        </span>
        <span className="hidden max-w-[12rem] flex-col sm:flex">
          <span className="truncate text-xs font-medium text-brand-900">{email}</span>
          <span className="flex items-center gap-1 text-[11px] text-success">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-success" />
            {isAdmin ? "Quản trị viên" : "Đã đăng nhập"}
          </span>
        </span>
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" className="size-4 text-muted">
          <path d="m6 8 4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-56 overflow-hidden rounded-xl border border-line bg-white py-1 shadow-lg"
        >
          <p className="truncate px-4 py-2 text-xs text-muted">{email}</p>
          <Link
            href="/settings"
            role="menuitem"
            className="block px-4 py-2 text-sm text-ink hover:bg-surface"
            onClick={() => setOpen(false)}
          >
            Cài đặt tài khoản
          </Link>
          {isAdmin ? (
            <Link
              href="/admin"
              role="menuitem"
              className="block px-4 py-2 text-sm text-ink hover:bg-surface"
              onClick={() => setOpen(false)}
            >
              Trang quản trị
            </Link>
          ) : null}
          <button
            type="button"
            role="menuitem"
            className="block w-full px-4 py-2 text-left text-sm text-danger hover:bg-danger-soft"
            onClick={async () => {
              setOpen(false);
              await signOut();
              router.replace("/login");
              router.refresh();
            }}
          >
            Đăng xuất
          </button>
        </div>
      ) : null}
    </div>
  );
}
