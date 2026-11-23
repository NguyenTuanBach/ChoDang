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
import { Async, Badge, Button, Card, DecisionPanel, Empty, Page, Row, StatusBadge } from "@/components/ui/ui";

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

function FlagsView({ base, initialStatus }: { base: "/lecturer" | "/admin"; initialStatus: string }) {
  const [status, setStatus] = useState(initialStatus);
  const state = useApi<Flag[]>(status ? `/api/flags?status=${status}` : "/api/flags");
  return (
    <Page title="Cờ rủi ro">
      <Row>
        {FILTERS.map((f) => (
          <Button key={f.value || "all"} variant={status === f.value ? "primary" : "default"} onClick={() => setStatus(f.value)}>
            {f.label}
          </Button>
        ))}
      </Row>
      <Async state={state}>
        {(list) =>
          list.length === 0 ? (
            <Card>
              <Empty>Không có cờ nào.</Empty>
            </Card>
          ) : (
            list.map((f) => (
              <Card key={f.id} title={`${f.student_name} — ${FLAG_KIND[f.kind] ?? f.kind}`} actions={<FlagActions flag={f} reload={state.reload} />}>
                <Row>
                  <StatusBadge kind="severity" value={f.severity} />
                  <StatusBadge kind="flag" value={f.status} />
                  <Badge>{f.created_by_kind === "agent" ? "Do AI đề xuất" : "Do hệ thống phát hiện"}</Badge>
                  <span>{fmtDateTime(f.created_at)}</span>
                </Row>
                <p>{f.reason}</p>
                {f.suggestion && <p>Gợi ý: {f.suggestion}</p>}
                {f.decision_reason && <p>Lý do xử lý: {f.decision_reason}</p>}
                <p>
                  <Link href={`${base}/internships/${f.internship_id}`}>Xem hồ sơ</Link>
                </p>
              </Card>
            ))
          )
        }
      </Async>
    </Page>
  );
}
