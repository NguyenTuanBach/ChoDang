"use client";

import Link from "next/link";
import { useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { JourneyStep } from "@/lib/journey";
import { FLAG_STATUS, INTERNSHIP_STATUS, MILESTONE_STATUS, OUTLINE_STATUS, REQUEST_STATUS, SEVERITY } from "@/lib/labels";

// Bộ thành phần giao diện dùng chung (Tailwind). Các trang chỉ ghép các thành phần này nên diện mạo thống nhất.
// Màu trạng thái: xanh = xong, vàng = chờ người khác, cam = cần bạn làm, đỏ = quá hạn/bị chặn, xám = chưa tới/đã đóng.

export function Page({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 pb-16 pt-6 sm:px-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="m-0 text-2xl font-bold tracking-tight">{title}</h1>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className="space-y-4">{children}</div>
    </main>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4 shadow-sm sm:p-5">
      {title && <h2 className="mb-3 mt-0 text-base font-semibold">{title}</h2>}
      {children}
    </section>
  );
}

export function Cols({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 md:grid-cols-2">{children}</div>;
}

export function Row({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2">{children}</div>;
}

export type Tone = "neutral" | "good" | "warn" | "action" | "bad";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "bg-soft text-muted ring-border",
  good: "bg-green-50 text-green-800 ring-green-600/30 dark:bg-green-950 dark:text-green-300",
  warn: "bg-amber-50 text-amber-800 ring-amber-600/30 dark:bg-amber-950 dark:text-amber-300",
  action: "bg-orange-50 text-orange-800 ring-orange-600/30 dark:bg-orange-950 dark:text-orange-300",
  bad: "bg-red-50 text-red-800 ring-red-600/30 dark:bg-red-950 dark:text-red-300",
};

const TONE_ICON: Record<Tone, string> = { neutral: "○", good: "✓", warn: "…", action: "!", bad: "✕" };

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASS[tone]}`}>
      <span aria-hidden="true">{TONE_ICON[tone]}</span>
      {children}
    </span>
  );
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
  revision_requested: "action",
  submitted: "warn",
  pending_credit: "warn",
  credit_review: "warn",
  open: "warn",
  warning: "action",
  invited: "warn",
  pending: "neutral",
  draft: "neutral",
  info: "neutral",
  acknowledged: "neutral",
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
    <label className="mb-3 flex flex-col gap-1 text-sm [&>input]:w-full [&>select]:w-full [&>textarea]:w-full">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

const BUTTON_VARIANT = {
  default: "border-border bg-bg text-fg hover:bg-soft",
  primary: "border-blue-600 bg-blue-600 text-white hover:bg-blue-700",
  danger: "border-red-600 bg-red-600 text-white hover:bg-red-700",
} as const;

export function Button({
  children,
  variant = "default",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof BUTTON_VARIANT }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-1 rounded-lg border px-3.5 py-1.5 text-sm font-medium shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_VARIANT[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function ErrorText({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="my-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 ring-1 ring-inset ring-red-600/20 dark:bg-red-950 dark:text-red-300">
      {message}
    </p>
  ) : null;
}

export function OkText({ message }: { message: string | null }) {
  return message ? (
    <p className="my-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800 ring-1 ring-inset ring-green-600/20 dark:bg-green-950 dark:text-green-300">
      {message}
    </p>
  ) : null;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="my-1 rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted">{children}</p>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <span className="text-muted">{children}</span>;
}

export function Pre({ children }: { children: ReactNode }) {
  return <p className="m-0 whitespace-pre-wrap break-words">{children}</p>;
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-bg">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-soft text-xs uppercase tracking-wide text-muted">
          <tr>
            {head.map((h, i) => (
              <th key={`${h}-${i}`} className="px-3 py-2 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr:hover]:bg-soft/60 [&>tr]:border-t [&>tr]:border-border [&_td]:px-3 [&_td]:py-2 [&_td]:align-top">{children}</tbody>
      </table>
    </div>
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
  if (state.loading && !state.data) {
    return (
      <p role="status" className="my-2 flex items-center gap-2 text-sm text-muted">
        <span className="inline-block size-4 animate-spin rounded-full border-2 border-border border-t-blue-600" aria-hidden="true" />
        Đang tải...
      </p>
    );
  }
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
    <div className="mt-2 rounded-xl border border-dashed border-border bg-bg p-3">
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
    <div className="h-2 overflow-hidden rounded-full bg-soft" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function DownloadLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} download className="text-blue-600 underline-offset-2 hover:underline">
      {children}
    </a>
  );
}

const STEP_DOT: Record<JourneyStep["state"], string> = {
  done: "border-green-600 bg-green-600 text-white",
  current: "border-blue-600 bg-blue-600 text-white ring-4 ring-blue-600/20",
  failed: "border-red-600 bg-red-600 text-white",
  todo: "border-border bg-bg text-muted",
};

// Thanh tiến trình hành trình: bước xong có dấu ✓, bước hiện tại tô đậm, bước chưa tới mờ.
export function Stepper({ steps }: { steps: JourneyStep[] }) {
  return (
    <ol className="m-0 flex list-none items-start p-0" aria-label="Hành trình thực tập">
      {steps.map((step, i) => (
        <li key={step.key} className="relative flex flex-1 flex-col items-center gap-1.5 text-center" aria-current={step.state === "current" ? "step" : undefined}>
          {i > 0 && <span aria-hidden="true" className={`absolute right-1/2 top-4 -z-0 h-0.5 w-full ${steps[i - 1].state === "done" ? "bg-green-600" : "bg-border"}`} />}
          <span className={`relative z-10 flex size-8 items-center justify-center rounded-full border-2 text-sm font-semibold ${STEP_DOT[step.state]}`}>
            {step.state === "done" ? "✓" : step.state === "failed" ? "✕" : i + 1}
          </span>
          <span className={`text-xs sm:text-sm ${step.state === "todo" ? "text-muted" : "font-semibold"}`}>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

// Liên kết có dạng nút (dùng cho hành động chính điều hướng sang trang khác).
export function LinkButton({ href, children, variant = "primary" }: { href: string; children: ReactNode; variant?: "primary" | "default" }) {
  const cls = variant === "primary" ? "border-blue-600 bg-blue-600 text-white hover:bg-blue-700" : "border-border bg-bg text-fg hover:bg-soft";
  return (
    <Link href={href} className={`inline-flex items-center justify-center rounded-lg border px-4 py-2 text-sm font-medium shadow-sm transition-colors ${cls}`}>
      {children}
    </Link>
  );
}
