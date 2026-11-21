"use client";

import Link from "next/link";
import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { FLAG_KIND, fmtDateTime } from "@/lib/labels";
import type { Flag } from "@/lib/types";
import { Async, Badge, Button, Card, DecisionPanel, Empty, Page, Row, StatusBadge } from "@/components/ui/ui";

const FILTERS = [
  { value: "open", label: "Mới" },
  { value: "acknowledged", label: "Đã ghi nhận" },
  { value: "resolved", label: "Đã giải quyết" },
  { value: "dismissed", label: "Đã bác bỏ" },
  { value: "", label: "Tất cả" },
];

export function FlagActions({ flag, reload }: { flag: Flag; reload: () => void }) {
  const [dismissing, setDismissing] = useState(false);
  const action = useAction(() => {
    setDismissing(false);
    reload();
  });
  if (flag.status === "resolved" || flag.status === "dismissed") return null;
  return (
    <>
      <Row>
        {flag.status === "open" && (
          <Button disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/flags/${flag.id}/decision`, { action: "acknowledge" }))}>
            Ghi nhận
          </Button>
        )}
        <Button variant="primary" disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/flags/${flag.id}/decision`, { action: "resolve" }))}>
          Đã giải quyết
        </Button>
        <Button variant="danger" disabled={action.busy} onClick={() => setDismissing(true)}>
          Bác bỏ
        </Button>
      </Row>
      {dismissing && (
        <DecisionPanel
          confirmLabel="Bác bỏ cờ"
          requireReason
          variant="danger"
          busy={action.busy}
          error={action.error}
          onCancel={() => setDismissing(false)}
          onSubmit={(reason) => void action.run(() => send("POST", `/api/flags/${flag.id}/decision`, { action: "dismiss", reason }))}
        />
      )}
    </>
  );
}

// Cờ rủi ro do hệ thống/agent tạo; chỉ người (GV/QTV) mới ghi nhận, giải quyết hoặc bác bỏ (C4, C8).
export default function FlagsPanel({ base }: { base: "/lecturer" | "/admin" }) {
  const [status, setStatus] = useState("open");
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
              <Card key={f.id} title={`${f.student_name} — ${FLAG_KIND[f.kind] ?? f.kind}`}>
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
                <FlagActions flag={f} reload={state.reload} />
              </Card>
            ))
          )
        }
      </Async>
    </Page>
  );
}
