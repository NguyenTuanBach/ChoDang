"use client";

import { MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { FLAG_KIND, fmtDateTime } from "@/lib/labels";
import type { Flag } from "@/lib/types";
import FormDialog from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { buttonVariants } from "@/components/ui/button";
import { Async, Button, Card, DecisionPanel, Empty, Page, Row } from "@/components/ui/ui";
import { cn } from "@/lib/utils";

const FILTERS = [
  { value: "open", label: "Mới" },
  { value: "acknowledged", label: "Đã ghi nhận" },
  { value: "resolved", label: "Đã giải quyết" },
  { value: "dismissed", label: "Đã bác bỏ" },
  { value: "", label: "Tất cả" },
];

// Hành động trên một cờ gom vào menu ba chấm (ghi nhận, đã giải quyết, bác bỏ); bác bỏ cần lý do nên mở hộp thoại.
export function FlagActions({ flag, reload }: { flag: Flag; reload: () => void }) {
  const [dismissing, setDismissing] = useState(false);
  const action = useAction(() => {
    setDismissing(false);
    reload();
  });
  if (flag.status === "resolved" || flag.status === "dismissed") return null;
  const decide = (name: "acknowledge" | "resolve") => void action.run(() => send("POST", `/api/flags/${flag.id}/decision`, { action: name }));
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            disabled={action.busy}
            aria-label="Hành động"
            className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg border-2 border-foreground/25 bg-card text-foreground shadow-xs hover:bg-secondary disabled:opacity-50"
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {flag.status === "open" && <DropdownMenuItem onSelect={() => decide("acknowledge")}>Ghi nhận</DropdownMenuItem>}
          <DropdownMenuItem onSelect={() => decide("resolve")}>Đã giải quyết</DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={() => setDismissing(true)}>
            Bác bỏ
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <FormDialog title="Bác bỏ cờ" open={dismissing} onOpenChange={setDismissing}>
        <DecisionPanel
          confirmLabel="Bác bỏ cờ"
          requireReason
          variant="danger"
          busy={action.busy}
          error={action.error}
          onCancel={() => setDismissing(false)}
          onSubmit={(reason) => void action.run(() => send("POST", `/api/flags/${flag.id}/decision`, { action: "dismiss", reason }))}
        />
      </FormDialog>
      {!dismissing && action.error ? <span className="text-xs text-destructive">{action.error}</span> : null}
    </>
  );
}

// Cờ rủi ro do hệ thống/agent tạo; chỉ người (GV/QTV) mới ghi nhận, giải quyết hoặc bác bỏ (C4, C8).
// Bộ lọc ban đầu lấy từ `?status=` (trợ lý mở trang kèm bộ lọc; `all` = tất cả); giá trị lạ thì "Mới". Query đổi thì dựng lại phần thân.
export default function FlagsPanel({ base }: { base: "/lecturer" | "/admin" }) {
  return (
    <Suspense fallback={null}>
      <FlagsFromUrl base={base} />
    </Suspense>
  );
}

function FlagsFromUrl({ base }: { base: "/lecturer" | "/admin" }) {
  const raw = useSearchParams().get("status");
  const value = raw === "all" ? "" : raw;
  const initial = value !== null && FILTERS.some((f) => f.value === value) ? value : "open";
  return <FlagsView key={initial || "all"} base={base} initialStatus={initial} />;
}

const PERIODS = [
  { value: "all", label: "Mọi lúc", days: 0 },
  { value: "today", label: "Hôm nay", days: 1 },
  { value: "7", label: "7 ngày", days: 7 },
  { value: "30", label: "30 ngày", days: 30 },
];

function FlagsView({ base, initialStatus }: { base: "/lecturer" | "/admin"; initialStatus: string }) {
  const [status, setStatus] = useState(initialStatus);
  const [period, setPeriod] = useState("all");
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [now] = useState(() => Date.now());
  const state = useApi<Flag[]>(status ? `/api/flags?status=${status}` : "/api/flags");
  const days = PERIODS.find((p) => p.value === period)?.days ?? 0;
  // Lọc thời gian và "Gấp" (mức nghiêm trọng) làm ngay trên trình duyệt.
  const visible = (list: Flag[]) => {
    const since = days > 0 ? now - days * 24 * 60 * 60 * 1000 : 0;
    return list.filter((f) => (!urgentOnly || f.severity === "critical") && new Date(f.created_at).getTime() >= since);
  };
  return (
    <Page title="Rủi ro tiến độ">
      <Row>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Trạng thái</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {FILTERS.map((f) => (
              <option key={f.value || "all"} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Thời gian</span>
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <Button variant={urgentOnly ? "primary" : "default"} onClick={() => setUrgentOnly((v) => !v)}>
          Gấp
        </Button>
      </Row>
      <Async state={state}>
        {(all) => {
          const list = visible(all);
          return list.length === 0 ? (
            <Card>
              <Empty>Không có rủi ro nào.</Empty>
            </Card>
          ) : (
            list.map((f) => (
              <Card
                key={f.id}
                title={`${f.student_name} — ${FLAG_KIND[f.kind] ?? f.kind}`}
                className={f.severity === "critical" ? "border-l-[6px] border-l-destructive" : undefined}
                actions={<FlagActions flag={f} reload={state.reload} />}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="m-0 text-xs text-muted-foreground">{fmtDateTime(f.created_at)}</p>
                    <p className="mb-0 mt-2 text-sm">{f.reason}</p>
                    {f.suggestion && <p className="mb-0 mt-1 text-sm text-muted-foreground">Gợi ý: {f.suggestion}</p>}
                    {f.decision_reason && <p className="mb-0 mt-1 text-sm">Lý do xử lý: {f.decision_reason}</p>}
                  </div>
                  <Link href={`${base}/internships/${f.internship_id}`} className={cn(buttonVariants({ variant: "outline" }), "h-9 shrink-0 border-2 border-foreground/25 bg-card px-4 text-foreground no-underline shadow-xs hover:bg-secondary")}>
                    Mở
                  </Link>
                </div>
              </Card>
            ))
          );
        }}
      </Async>
    </Page>
  );
}
