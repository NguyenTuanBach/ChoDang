"use client";

import { ClipboardCheck, GraduationCap, ShieldCheck, Sparkles } from "lucide-react";
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
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-10 text-sidebar-foreground lg:flex" aria-hidden="true">
        <div className="absolute -right-24 -top-24 size-80 rounded-full bg-primary/30 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 size-96 rounded-full bg-chart-2/20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground">
            <GraduationCap className="size-6" />
          </span>
          <span className="text-lg font-semibold tracking-tight">VIN-15</span>
        </div>
        <div className="relative max-w-md space-y-6">
          <h2 className="m-0 text-3xl font-bold leading-tight tracking-tight text-white">Quản lý thực tập rõ ràng, có Trợ lý AI bên cạnh.</h2>
          <ul className="m-0 list-none space-y-4 p-0 text-sm">
            {[
              [ClipboardCheck, "Một hành trình rõ ràng từ hồ sơ, đề cương, nhật ký đến công nhận tín chỉ."],
              [Sparkles, "Trợ lý trả lời theo quy chế, kèm căn cứ; chỉ gợi ý, người có thẩm quyền mới quyết định."],
              [ShieldCheck, "Phân quyền theo vai trò, mọi thay đổi trạng thái đều được ghi lại."],
            ].map(([Icon, text], i) => {
              const I = Icon as typeof Sparkles;
              return (
                <li key={i} className="flex items-start gap-3">
                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10">
                    <I className="size-4" />
                  </span>
                  <span className="leading-relaxed opacity-90">{text as string}</span>
                </li>
              );
            })}
          </ul>
        </div>
        <p className="relative m-0 text-xs opacity-60">Hệ thống hỗ trợ thực tập</p>
      </aside>

      <main className="mx-auto flex w-full max-w-lg flex-col justify-center px-5 py-10 sm:py-16">
        <div className="mb-8">
          <p className="mb-1 flex items-center gap-2 text-sm font-bold tracking-tight text-primary lg:hidden">
            <GraduationCap className="size-5" aria-hidden="true" /> VIN-15
          </p>
          <h1 className="m-0 text-2xl font-bold tracking-tight">Đăng nhập VIN-15</h1>
          <p className="mt-2 text-sm text-muted-foreground">Hệ thống hỗ trợ thực tập</p>
        </div>

        <section className="mb-4 rounded-xl border-2 border-foreground/25 bg-card p-5 shadow-xs">
          <h2 className="mb-1 mt-0 text-base font-semibold">Đăng nhập bằng Google</h2>
          <p className="mb-3 mt-0 text-sm text-muted-foreground">
            Dành cho tài khoản đã được mời qua email.{google ? "" : " Chưa cấu hình GOOGLE_CLIENT_ID/SECRET ở BE."}
          </p>
          <button
            type="button"
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!google}
            onClick={() => window.location.assign("/api/auth/google/login")}
          >
            Đăng nhập Google
          </button>
        </section>

        {accounts === undefined && <p className="text-center text-sm text-muted-foreground">Đang tải...</p>}

        {accounts && (
          <section className="mb-4 rounded-xl border-2 border-foreground/25 bg-card p-5 shadow-xs" aria-labelledby="dev-login-title">
            <h2 id="dev-login-title" className="mb-1 mt-0 text-base font-semibold">
              Đăng nhập dev
            </h2>
            <p className="mb-4 mt-0 text-sm text-muted-foreground">Vào tài khoản mẫu cùng dữ liệu mẫu. Chỉ có ở môi trường dev.</p>
            {accounts.length === 0 && <p className="text-sm text-muted-foreground">Chưa có tài khoản mẫu: chạy make seed-dev.</p>}
            {ROLE_ORDER.map((role) => {
              const group = accounts.filter((account) => account.role === role);
              if (group.length === 0) return null;
              return (
                <div key={role} className="mb-4 last:mb-0">
                  <h3 className="mb-2 mt-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{ROLE_LABEL[role]}</h3>
                  <div className="grid gap-2">
                    {group.map((account) => (
                      <button
                        key={account.email}
                        type="button"
                        className="flex flex-col items-start rounded-lg border-2 border-foreground/25 bg-background px-3 py-2 text-left transition-colors hover:border-primary hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={busy !== null}
                        onClick={() => void signIn(account.email)}
                      >
                        <span className="text-sm font-medium">{account.full_name || account.email}</span>
                        <small className="text-xs text-muted-foreground">{account.email}</small>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </section>
        )}

        {error && (
          <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-destructive ring-1 ring-inset ring-destructive/20">
            {error}
          </p>
        )}
      </main>
    </div>
  );
}
