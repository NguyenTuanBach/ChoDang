"use client";

import { useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { FLAG_STATUS, INTERNSHIP_STATUS, MILESTONE_STATUS, OUTLINE_STATUS, REQUEST_STATUS, SEVERITY } from "@/lib/labels";
import styles from "./ui.module.css";

export function Page({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <main className={styles.page}>
      <div className={styles.pageHead}>
        <h1>{title}</h1>
        {actions && <div className={styles.row}>{actions}</div>}
      </div>
      {children}
    </main>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className={styles.card}>
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}

export function Cols({ children }: { children: ReactNode }) {
  return <div className={styles.cols}>{children}</div>;
}

export function Row({ children }: { children: ReactNode }) {
  return <div className={styles.row}>{children}</div>;
}

export type Tone = "neutral" | "good" | "warn" | "bad";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const toneClass = tone === "good" ? styles.good : tone === "warn" ? styles.warn : tone === "bad" ? styles.bad : "";
  return <span className={`${styles.badge} ${toneClass}`}>{children}</span>;
}

const TONES: Record<string, Tone> = {
  accepted: "good",
  approved: "good",
  completed: "good",
  resolved: "good",
  in_progress: "good",
  confirmed: "good",
  active: "good",
  synced: "good",
  rejected: "bad",
  overdue: "bad",
  closed_no_credit: "bad",
  revoked: "bad",
  failed: "bad",
  critical: "bad",
  dismissed: "neutral",
  revision_requested: "warn",
  submitted: "warn",
  pending_credit: "warn",
  credit_review: "warn",
  open: "warn",
  warning: "warn",
  invited: "warn",
  pending: "neutral",
};

const LABELS: Record<string, Record<string, string>> = {
  internship: INTERNSHIP_STATUS,
  milestone: MILESTONE_STATUS,
  outline: OUTLINE_STATUS,
  request: REQUEST_STATUS,
  flag: FLAG_STATUS,
  severity: SEVERITY,
};

export function StatusBadge({ kind, value }: { kind: keyof typeof LABELS | "raw"; value: string }) {
  const label = kind === "raw" ? value : (LABELS[kind]?.[value] ?? value);
  return <Badge tone={TONES[value] ?? "neutral"}>{label}</Badge>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className={styles.field}>
      <span>{label}</span>
      {children}
      {hint && <span className={styles.hint}>{hint}</span>}
    </label>
  );
}

export function Button({
  children,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "danger" }) {
  const cls = variant === "primary" ? styles.primary : variant === "danger" ? styles.danger : "";
  return (
    <button type="button" {...props} className={`${styles.btn} ${cls}`}>
      {children}
    </button>
  );
}

export function ErrorText({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className={styles.error}>
      {message}
    </p>
  ) : null;
}

export function OkText({ message }: { message: string | null }) {
  return message ? <p className={styles.ok}>{message}</p> : null;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className={styles.empty}>{children}</p>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <span className={styles.muted}>{children}</span>;
}

export function Pre({ children }: { children: ReactNode }) {
  return <p className={styles.pre}>{children}</p>;
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

export function Async<T>({
  state,
  children,
}: {
  state: { data: T | null; error: string | null; loading: boolean };
  children: (data: T) => ReactNode;
}) {
  if (state.error && !state.data) return <ErrorText message={state.error} />;
  if (state.loading && !state.data) return <Empty>Đang tải...</Empty>;
  if (!state.data) return null;
  return <>{children(state.data)}</>;
}

// Khung nhập lý do cho một quyết định (từ chối / yêu cầu sửa / không duyệt bắt buộc có lý do — BR-S2).
export function DecisionPanel({
  confirmLabel,
  requireReason,
  variant = "primary",
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  confirmLabel: string;
  requireReason: boolean;
  variant?: "primary" | "danger";
  busy: boolean;
  error: string | null;
  onSubmit: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const missing = requireReason && reason.trim() === "";
  return (
    <div className={styles.decision}>
      <Field label={requireReason ? "Lý do (bắt buộc)" : "Ghi chú (không bắt buộc)"}>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <ErrorText message={error} />
      <Row>
        <Button variant={variant} disabled={busy || missing} onClick={() => onSubmit(reason.trim())}>
          {confirmLabel}
        </Button>
        <Button onClick={onCancel} disabled={busy}>
          Hủy
        </Button>
      </Row>
    </div>
  );
}

// Nút chọn tệp: gọi onFile ngay khi chọn xong.
export function FilePicker({ label, accept, disabled, onFile }: { label: string; accept?: string; disabled?: boolean; onFile: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        accept={accept}
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
      <Button disabled={disabled} onClick={() => input.current?.click()}>
        {label}
      </Button>
    </>
  );
}

export function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className={styles.bar} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className={styles.barFill} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function DownloadLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} download>
      {children}
    </a>
  );
}
