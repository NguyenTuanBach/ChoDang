"use client";

import Link from "next/link";
import { AlertCircle, Check, Circle, Clock, Inbox, X, type LucideIcon } from "lucide-react";
import { useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Button as ShButton, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { JourneyStep } from "@/lib/journey";
import { FLAG_STATUS, INTERNSHIP_STATUS, MILESTONE_STATUS, OUTLINE_STATUS, REQUEST_STATUS, SEVERITY } from "@/lib/labels";
import { cn } from "@/lib/utils";

// Bộ thành phần giao diện dùng chung (shadcn/ui + Tailwind). Các trang chỉ ghép các thành phần này nên diện mạo thống nhất.
// Màu trạng thái: xanh lá = xong, vàng = chờ người khác, cam = cần bạn làm, đỏ = quá hạn/bị chặn, xám = chưa tới/đã đóng.

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="m-0 text-2xl font-bold tracking-tight">{title}</h1>
        {description && <p className="mb-0 mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Page({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pb-16 pt-6 sm:px-6">
      <PageHeader title={title} description={description} actions={actions} />
      <div className="space-y-5">{children}</div>
    </div>
  );
}

export function Card({ title, description, actions, children, className }: { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-xl border-2 border-foreground/25 bg-card text-card-foreground shadow-xs", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-foreground/25 px-4 py-2.5">
          <div className="min-w-0">
            {title && <h2 className="m-0 text-base font-semibold">{title}</h2>}
            {description && <p className="m-0 mt-0.5 text-xs text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
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
  neutral: "bg-muted text-muted-foreground ring-border",
  good: "bg-success-soft text-success ring-success/25",
  warn: "bg-warning-soft text-warning ring-warning/30",
  action: "bg-orange-100 text-orange-800 ring-orange-600/25 dark:bg-orange-950 dark:text-orange-300",
  bad: "bg-danger-soft text-destructive ring-destructive/25",
};

const TONE_ICON: Record<Tone, LucideIcon> = { neutral: Circle, good: Check, warn: Clock, action: AlertCircle, bad: X };

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const Icon = TONE_ICON[tone];
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", TONE_CLASS[tone])}>
      <Icon aria-hidden="true" className="size-3" />
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
    <label className="mb-3 flex flex-col gap-1.5 text-sm [&>input]:w-full [&>select]:w-full [&>textarea]:w-full">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

const BUTTON_VARIANT = {
  default: "outline",
  primary: "default",
  danger: "destructive",
} as const;

export function Button({
  children,
  variant = "default",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof BUTTON_VARIANT }) {
  return (
    <ShButton
      type="button"
      variant={BUTTON_VARIANT[variant]}
      {...props}
      className={cn("h-9 px-3.5 text-sm shadow-xs", variant === "danger" && "bg-destructive text-white hover:bg-destructive/90", className)}
    >
      {children}
    </ShButton>
  );
}

export function ErrorText({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="my-2 flex items-start gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-destructive ring-1 ring-inset ring-destructive/20">
      <X aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </p>
  ) : null;
}

export function OkText({ message }: { message: string | null }) {
  return message ? (
    <p className="my-2 flex items-start gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm text-success ring-1 ring-inset ring-success/20">
      <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </p>
  ) : null;
}

export function EmptyState({ title, children, icon: Icon = Inbox, action }: { title?: string; children?: ReactNode; icon?: LucideIcon; action?: ReactNode }) {
  return (
    <div className="my-1 flex flex-col items-center gap-2 rounded-xl border border-dashed border-border px-4 py-8 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      {title && <p className="m-0 text-sm font-medium">{title}</p>}
      {children && <p className="m-0 max-w-md text-sm text-muted-foreground">{children}</p>}
      {action}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <EmptyState>{children}</EmptyState>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <span className="text-muted-foreground">{children}</span>;
}

export function Pre({ children }: { children: ReactNode }) {
  return <p className="m-0 whitespace-pre-wrap break-words">{children}</p>;
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            {head.map((h, i) => (
              <th key={`${h}-${i}`} className="px-3 py-2.5 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr:hover]:bg-muted/50 [&>tr]:border-t [&>tr]:border-border [&_td]:px-3 [&_td]:py-2.5 [&_td]:align-top">{children}</tbody>
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
      <div role="status" className="space-y-3" aria-live="polite">
        <span className="sr-only">Đang tải...</span>
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
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
    <div className="mt-2 rounded-xl border border-dashed border-border bg-background p-3">
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

// Thanh tiến độ chỉ có hai màu: xanh lá = đã hoàn thành/đạt, đỏ = chưa hoàn thành (đang làm, chờ, trượt, quá hạn...).
const DONE_STATUS = new Set(["completed", "in_progress", "accepted", "approved", "lecturer_passed", "confirmed"]);

export function outcomeBg(status: string): string {
  return DONE_STATUS.has(status) ? "bg-green-600" : "bg-red-600";
}

export function ProgressBar({ value, max, status }: { value: number; max: number; status?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return <Progress value={pct} className="h-2.5 border border-foreground/25" indicatorClassName={status ? outcomeBg(status) : undefined} />;
}

export function DownloadLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} download className="text-primary underline-offset-2 hover:underline">
      {children}
    </a>
  );
}

const STEP_DOT: Record<JourneyStep["state"], string> = {
  done: "border-success bg-success text-white",
  current: "border-primary bg-primary text-primary-foreground ring-4 ring-primary/20",
  failed: "border-destructive bg-destructive text-white",
  todo: "border-border bg-card text-muted-foreground",
};

// Thanh tiến trình hành trình: bước xong có dấu ✓, bước hiện tại tô đậm, bước chưa tới mờ.
export function Stepper({ steps }: { steps: JourneyStep[] }) {
  return (
    <ol className="m-0 flex list-none items-start p-0" aria-label="Hành trình thực tập">
      {steps.map((step, i) => (
        <li key={step.key} className="relative flex flex-1 flex-col items-center gap-1.5 text-center" aria-current={step.state === "current" ? "step" : undefined}>
          {i > 0 && <span aria-hidden="true" className={cn("absolute right-1/2 top-4 -z-0 h-0.5 w-full", steps[i - 1].state === "done" ? "bg-success" : "bg-border")} />}
          <span className={cn("relative z-10 flex size-8 items-center justify-center rounded-full border-2 text-sm font-semibold", STEP_DOT[step.state])}>
            {step.state === "done" ? <Check aria-hidden="true" className="size-4" /> : step.state === "failed" ? <X aria-hidden="true" className="size-4" /> : i + 1}
          </span>
          <span className={cn("text-xs sm:text-sm", step.state === "todo" ? "text-muted-foreground" : "font-semibold")}>{step.label}</span>
        </li>
      ))}
    </ol>
  );
}

// Liên kết có dạng nút (dùng cho hành động chính điều hướng sang trang khác).
export function LinkButton({ href, children, variant = "primary" }: { href: string; children: ReactNode; variant?: "primary" | "default" }) {
  return (
    <Link href={href} className={cn(buttonVariants({ variant: variant === "primary" ? "default" : "outline", size: "lg" }), "h-9 px-4 shadow-xs")}>
      {children}
    </Link>
  );
}

const STAT_TONE: Record<"default" | "good" | "warn" | "bad", string> = {
  default: "bg-accent text-accent-foreground",
  good: "bg-success-soft text-success",
  warn: "bg-warning-soft text-warning",
  bad: "bg-danger-soft text-destructive",
};

// Ô số liệu (KPI) của trang tổng quan: nhãn nhỏ, số lớn, ghi chú ngắn, biểu tượng nền nhạt. Có `href` thì cả ô là liên kết.
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  href,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "good" | "warn" | "bad";
  href?: string;
}) {
  const body = (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="m-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mb-0 mt-1.5 text-2xl font-bold leading-none tracking-tight">{value}</p>
        {hint && <p className="mb-0 mt-1.5 text-xs text-muted-foreground">{hint}</p>}
      </div>
      {Icon && (
        <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", STAT_TONE[tone])}>
          <Icon aria-hidden="true" className="size-5" />
        </span>
      )}
    </div>
  );
  const cls = "block rounded-xl border-2 border-foreground/25 bg-card p-4 text-card-foreground shadow-xs";
  return href ? (
    <Link href={href} className={cn(cls, "transition-colors hover:bg-accent/60")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}
