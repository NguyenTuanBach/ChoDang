"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { devLogin, fetchProviders, listDevAccounts, ROLE_LABEL, type AuthUser, type Role } from "@/lib/auth";

const ROLE_ORDER: Role[] = ["admin", "lecturer", "student"];

export default function LoginPanel({ fetchImpl }: { fetchImpl?: typeof fetch }) {
  const router = useRouter();
  // undefined: đang tải; null: BE không bật đăng nhập dev; mảng: danh sách tài khoản mẫu.
  const [accounts, setAccounts] = useState<AuthUser[] | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [google, setGoogle] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchProviders(fetchImpl).then((p) => {
      if (!cancelled) setGoogle(p.google);
    });
    // Google chuyển về /login?error=... khi đăng nhập thất bại (vd email chưa được mời).
    queueMicrotask(() => {
      const message = new URLSearchParams(window.location.search).get("error");
      if (!cancelled && message) setError(message);
    });
    listDevAccounts(fetchImpl)
      .then((list) => {
        if (!cancelled) setAccounts(list);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setAccounts(null);
        setError(e instanceof Error ? e.message : "Không kết nối được BE");
      });
    return () => {
      cancelled = true;
    };
  }, [fetchImpl]);

  async function signIn(email: string) {
    setBusy(email);
    setError(null);
    try {
      await devLogin(email, fetchImpl);
      router.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Đăng nhập thất bại");
      setBusy(null);
    }
  }

  return (
    <main className="mx-auto w-full max-w-lg px-4 py-10 sm:py-16">
      <div className="mb-8 text-center">
        <p className="mb-1 text-sm font-bold tracking-tight text-blue-600">VIN-15</p>
        <h1 className="m-0 text-2xl font-bold tracking-tight">Đăng nhập VIN-15</h1>
        <p className="mt-2 text-sm text-muted">Hệ thống hỗ trợ thực tập</p>
      </div>

      <section className="mb-4 rounded-xl border border-border bg-surface p-5 shadow-sm">
        <h2 className="mb-1 mt-0 text-base font-semibold">Đăng nhập bằng Google</h2>
        <p className="mb-3 mt-0 text-sm text-muted">
          Dành cho tài khoản đã được mời qua email.{google ? "" : " Chưa cấu hình GOOGLE_CLIENT_ID/SECRET ở BE."}
        </p>
        <button
          type="button"
          className="w-full rounded-lg border border-blue-600 bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!google}
          onClick={() => window.location.assign("/api/auth/google/login")}
        >
          Đăng nhập Google
        </button>
      </section>

      {accounts === undefined && <p className="text-center text-sm text-muted">Đang tải...</p>}

      {accounts && (
        <section className="mb-4 rounded-xl border border-border bg-surface p-5 shadow-sm" aria-labelledby="dev-login-title">
          <h2 id="dev-login-title" className="mb-1 mt-0 text-base font-semibold">
            Đăng nhập dev
          </h2>
          <p className="mb-4 mt-0 text-sm text-muted">Vào tài khoản mẫu cùng dữ liệu mẫu. Chỉ có ở môi trường dev.</p>
          {accounts.length === 0 && <p className="text-sm text-muted">Chưa có tài khoản mẫu: chạy make seed-dev.</p>}
          {ROLE_ORDER.map((role) => {
            const group = accounts.filter((account) => account.role === role);
            if (group.length === 0) return null;
            return (
              <div key={role} className="mb-4 last:mb-0">
                <h3 className="mb-2 mt-0 text-xs font-semibold uppercase tracking-wide text-muted">{ROLE_LABEL[role]}</h3>
                <div className="grid gap-2">
                  {group.map((account) => (
                    <button
                      key={account.email}
                      type="button"
                      className="flex flex-col items-start rounded-lg border border-border bg-bg px-3 py-2 text-left transition-colors hover:border-blue-600 hover:bg-soft disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={busy !== null}
                      onClick={() => void signIn(account.email)}
                    >
                      <span className="text-sm font-medium">{account.full_name || account.email}</span>
                      <small className="text-xs text-muted">{account.email}</small>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 ring-1 ring-inset ring-red-600/20 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}
    </main>
  );
}
