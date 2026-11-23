"use client";

import { Paperclip } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import type { RequestItem } from "@/lib/types";
import { buttonVariants } from "@/components/ui/button";
import { Async, Button, Card, DecisionPanel, Empty, Page, Row } from "@/components/ui/ui";
import { cn } from "@/lib/utils";
import DownloadDoc from "@/components/student/DownloadDoc";

// Yêu cầu chờ duyệt: GV duyệt loại thường, QTV duyệt loại ảnh hưởng tín chỉ (D13).
export default function RequestsReview({ base }: { base: "/lecturer" | "/admin" }) {
  const state = useApi<RequestItem[]>("/api/requests/pending");
  return (
    <Page title="Yêu cầu chờ duyệt">
      <Async state={state}>
        {(list) =>
          list.length === 0 ? (
            <Card>
              <Empty>Không có yêu cầu nào đang chờ.</Empty>
            </Card>
          ) : (
            list.map((r) => <Item key={r.id} item={r} base={base} reload={state.reload} />)
          )
        }
      </Async>
    </Page>
  );
}

export function RequestDecision({ item, reload }: { item: RequestItem; reload: () => void }) {
  const [mode, setMode] = useState<"approve" | "reject" | null>(null);
  const action = useAction(() => {
    setMode(null);
    reload();
  });
  return (
    <>
      {mode === null && (
        <Row>
          <Button variant="primary" onClick={() => setMode("approve")}>
            Duyệt
          </Button>
          <Button variant="danger" onClick={() => setMode("reject")}>
            Từ chối
          </Button>
        </Row>
      )}
      {mode && (
        <DecisionPanel
          confirmLabel={mode === "approve" ? "Xác nhận duyệt" : "Xác nhận từ chối"}
          requireReason={mode === "reject"}
          variant={mode === "approve" ? "primary" : "danger"}
          busy={action.busy}
          error={action.error}
          onCancel={() => setMode(null)}
          onSubmit={(reason) => void action.run(() => send("POST", `/api/requests/${item.id}/decision`, { approve: mode === "approve", reason }))}
        />
      )}
    </>
  );
}

function Item({ item, base, reload }: { item: RequestItem; base: string; reload: () => void }) {
  return (
    <Card title={`${item.student_name} — ${item.kind === "milestone_extension" ? `xin gia hạn mốc ${item.milestone_code}` : item.exception_type_name}`}>
      <div className="flex items-start justify-between gap-4">
        <dl className="m-0 grid min-w-0 flex-1 grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="font-medium text-muted-foreground">Gửi lúc</dt>
          <dd className="m-0">{fmtDateTime(item.created_at)}</dd>
          {item.new_due_date && (
            <>
              <dt className="font-medium text-muted-foreground">Hạn mới đề nghị</dt>
              <dd className="m-0">{fmtDate(item.new_due_date)}</dd>
            </>
          )}
          <dt className="font-medium text-muted-foreground">Lý do</dt>
          <dd className="m-0 whitespace-pre-wrap break-words">{item.reason}</dd>
          {item.affects_credit && (
            <>
              <dt className="font-medium text-muted-foreground">Người duyệt</dt>
              <dd className="m-0">Quản trị viên (ảnh hưởng tín chỉ)</dd>
            </>
          )}
          {item.attachments.length > 0 && (
            <>
              <dt className="font-medium text-muted-foreground">Tệp đính kèm</dt>
              <dd className="m-0 space-y-1">
                {item.attachments.map((a) => (
                  <div key={a.id} className="flex items-center gap-1.5">
                    <Paperclip className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <DownloadDoc href={`/api/request-attachments/${a.id}/download`} name={a.filename} />
                  </div>
                ))}
              </dd>
            </>
          )}
        </dl>
        <Link href={`${base}/internships/${item.internship_id}`} className={cn(buttonVariants({ variant: "outline" }), "h-9 shrink-0 border-2 border-foreground/25 bg-card px-4 text-foreground no-underline shadow-xs hover:bg-secondary")}>
          Mở
        </Link>
      </div>
      <div className="mt-4 border-t border-foreground/15 pt-4">
        <RequestDecision item={item} reload={reload} />
      </div>
    </Card>
  );
}
