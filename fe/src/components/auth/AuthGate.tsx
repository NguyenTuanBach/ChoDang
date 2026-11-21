"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { fetchMe, logout, ROLE_LABEL, type AuthUser, type Role } from "@/lib/auth";
import { HOME, NAV } from "@/lib/nav";
import { UserContext } from "@/lib/user-context";
import styles from "./auth.module.css";

type Props = {
  children: ReactNode;
  fetchImpl?: typeof fetch;
  // Chỉ các vai trò này vào được trang; vai trò khác bị chuyển về trang chủ của họ. Bỏ trống = mọi vai trò.
  roles?: Role[];
};

// Chặn trang cho người chưa đăng nhập (chuyển sang /login), kiểm vai trò, hiện thanh "menu · thông báo · tên · vai trò · Đăng xuất"
// và cung cấp người dùng cho trang con qua useCurrentUser().
export default function AuthGate({ children, fetchImpl, roles }: Props) {
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
        else if (roles && !roles.includes(me.role)) router.replace(HOME[me.role]);
        else setUser(me);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Không kết nối được BE");
      });
    return () => {
      cancelled = true;
    };
  }, [fetchImpl, router, roles]);

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

  async function signOut() {
    try {
      await logout(fetchImpl);
    } catch {
      // phiên có thể đã hết hạn: vẫn về trang đăng nhập
    }
    router.replace("/login");
  }

  if (error) {
    return (
      <p role="alert" className={`${styles.status} ${styles.error}`}>
        Không kiểm tra được phiên đăng nhập: {error}
      </p>
    );
  }
  if (!user) return <p className={styles.status}>Đang kiểm tra đăng nhập...</p>;

  return (
    <UserContext.Provider value={user}>
      <header className={styles.bar}>
        <nav className={styles.nav} aria-label="Menu chính">
          {NAV[user.role].map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className={styles.who}>
          <Link href="/notifications" className={styles.bell}>
            Thông báo{unread > 0 && <span className={styles.badge}>{unread}</span>}
          </Link>
          <strong>{user.full_name || user.email}</strong>
          <span className={styles.role}>{ROLE_LABEL[user.role]}</span>
          <button type="button" onClick={() => void signOut()}>
            Đăng xuất
          </button>
        </div>
      </header>
      {children}
    </UserContext.Provider>
  );
}
