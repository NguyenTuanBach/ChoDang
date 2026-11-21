"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { fetchMe, logout, ROLE_LABEL, type AuthUser } from "@/lib/auth";
import styles from "./auth.module.css";

type Props = { children: ReactNode; fetchImpl?: typeof fetch };

// Chặn trang cho người chưa đăng nhập (chuyển sang /login) và hiện thanh "tên · vai trò · Đăng xuất".
export default function AuthGate({ children, fetchImpl }: Props) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMe(fetchImpl)
      .then((me) => {
        if (cancelled) return;
        if (me) setUser(me);
        else router.replace("/login");
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Không kết nối được BE");
      });
    return () => {
      cancelled = true;
    };
  }, [fetchImpl, router]);

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
    <>
      <header className={styles.bar}>
        <div className={styles.who}>
          <strong>{user.full_name || user.email}</strong>
          <span className={styles.role}>{ROLE_LABEL[user.role]}</span>
        </div>
        <button type="button" onClick={() => void signOut()}>
          Đăng xuất
        </button>
      </header>
      {children}
    </>
  );
}
