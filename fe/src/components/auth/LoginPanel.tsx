"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { devLogin, listDevAccounts, ROLE_LABEL, type AuthUser, type Role } from "@/lib/auth";
import styles from "./auth.module.css";

const ROLE_ORDER: Role[] = ["admin", "lecturer", "student"];

export default function LoginPanel({ fetchImpl }: { fetchImpl?: typeof fetch }) {
  const router = useRouter();
  // undefined: đang tải; null: BE không bật đăng nhập dev; mảng: danh sách tài khoản mẫu.
  const [accounts, setAccounts] = useState<AuthUser[] | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
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
    <main className={styles.login}>
      <h1>Đăng nhập VIN-15</h1>

      <section className={styles.section}>
        <h2>Đăng nhập bằng Google</h2>
        <p className={styles.hint}>Dành cho tài khoản đã được mời qua email. Chưa bật ở bản này.</p>
        <button type="button" className={styles.google} disabled>
          Đăng nhập Google
        </button>
      </section>

      {accounts === undefined && <p className={styles.hint}>Đang tải...</p>}

      {accounts && (
        <section className={styles.section} aria-labelledby="dev-login-title">
          <h2 id="dev-login-title">Đăng nhập dev</h2>
          <p className={styles.hint}>Vào tài khoản mẫu cùng dữ liệu mẫu. Chỉ có ở môi trường dev.</p>
          {accounts.length === 0 && <p className={styles.hint}>Chưa có tài khoản mẫu: chạy make seed-dev.</p>}
          {ROLE_ORDER.map((role) => {
            const group = accounts.filter((account) => account.role === role);
            if (group.length === 0) return null;
            return (
              <div key={role} className={styles.group}>
                <h3>{ROLE_LABEL[role]}</h3>
                <div className={styles.accounts}>
                  {group.map((account) => (
                    <button
                      key={account.email}
                      type="button"
                      className={styles.account}
                      disabled={busy !== null}
                      onClick={() => void signIn(account.email)}
                    >
                      <span>{account.full_name || account.email}</span>
                      <small>{account.email}</small>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      )}

      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
    </main>
  );
}
