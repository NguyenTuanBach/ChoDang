"use client";

import Link from "next/link";
import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import type { RequestItem } from "@/lib/types";
import { Async, Badge, Button, Card, DecisionPanel, Empty, Page, Row } from "@/components/ui/ui";
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
      <Row>
        {item.affects_credit && <Badge tone="warn">Ảnh hưởng tín chỉ</Badge>}
        <span>Gửi lúc {fmtDateTime(item.created_at)}</span>
        {item.new_due_date && <span>Hạn mới đề nghị: {fmtDate(item.new_due_date)}</span>}
      </Row>
      <p>Lý do: {item.reason}</p>
      {item.attachments.map((a) => (
        <div key={a.id}>
          <DownloadDoc href={`/api/request-attachments/${a.id}/download`} name={a.filename} />
        </div>
      ))}
      <p>
        <Link href={`${base}/internships/${item.internship_id}`}>Xem hồ sơ và lịch sử</Link>
      </p>
      <RequestDecision item={item} reload={reload} />
    </Card>
  );
}
