"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchMe, logout, type AuthUser } from "@/lib/auth";
import { SessionContext, UserContext } from "@/lib/user-context";

type Props = { children: ReactNode; fetchImpl?: typeof fetch };

// Chặn người chưa đăng nhập (chuyển sang /login) và cung cấp người dùng + số thông báo chưa đọc cho cả khung ứng dụng.
// Đặt ở layout của nhóm (app) nên chỉ chạy một lần khi vào, không chạy lại mỗi lần chuyển trang.
export default function AuthProvider({ children, fetchImpl }: Props) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchMe(fetchImpl)
      .then((me) => {
        if (cancelled) return;
        if (!me) router.replace("/login");
        else setUser(me);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Không kết nối được BE");
      });
    return () => {
      cancelled = true;
    };
  }, [fetchImpl, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (fetchImpl ?? fetch)("/api/notifications", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body: { unread?: number } | null) => {
        if (!cancelled) setUnread(body?.unread ?? 0);
      })
      .catch(() => undefined); // thông báo không chặn trang
    return () => {
      cancelled = true;
    };
  }, [user, fetchImpl]);

  const signOut = useCallback(async () => {
    try {
      await logout(fetchImpl);
    } catch {
      // phiên có thể đã hết hạn: vẫn về trang đăng nhập
    }
    router.replace("/login");
  }, [fetchImpl, router]);

  const session = useMemo(() => (user ? { user, unread, signOut } : null), [user, unread, signOut]);

  if (error) {
    return (
      <p role="alert" className="mx-auto my-12 max-w-2xl px-4 text-destructive">
        Không kiểm tra được phiên đăng nhập: {error}
      </p>
    );
  }
  if (!user || !session) {
    return (
      <div role="status" className="mx-auto my-12 max-w-2xl space-y-3 px-4">
        <p className="text-sm text-muted-foreground">Đang kiểm tra đăng nhập...</p>
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <UserContext.Provider value={user}>
      <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
    </UserContext.Provider>
  );
}
