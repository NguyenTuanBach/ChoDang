"use client";

import { useState } from "react";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate } from "@/lib/labels";
import type { InternshipDetail, Milestone } from "@/lib/types";
import { Async, Button, Card, Empty, ErrorText, Field, FilePicker, Page, Row, StatusBadge } from "@/components/ui/ui";
import DownloadDoc from "./DownloadDoc";

export default function MilestonesPage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Mốc và minh chứng">
      <Async state={state}>
        {(d) =>
          !d.internship ? (
            <Empty>Bạn chưa có hồ sơ thực tập.</Empty>
          ) : d.milestones.length === 0 ? (
            <Empty>Mốc sẽ xuất hiện sau khi giảng viên xác nhận hồ sơ.</Empty>
          ) : (
            d.milestones.map((m) => <MilestoneCard key={m.id} milestone={m} detail={d} reload={state.reload} />)
          )
        }
      </Async>
    </Page>
  );
}

function MilestoneCard({ milestone: m, detail, reload }: { milestone: Milestone; detail: InternshipDetail; reload: () => void }) {
  const evidence = detail.evidence.filter((e) => e.milestone_code === m.code);
  const working = ["in_progress", "pending_credit"].includes(detail.internship?.status ?? "");
  const locked = m.stored_status === "submitted" || m.stored_status === "accepted";
  const up = useAction(reload);
  const submit = useAction(reload);
  const [extending, setExtending] = useState(false);

  return (
    <Card title={`${m.code} — ${m.name}`}>
      <Row>
        <StatusBadge kind="milestone" value={m.status} />
        <span>Hạn {fmtDate(m.due_date)}</span>
      </Row>
      <p>{m.next_action}</p>
      {m.note && <p>Nhận xét của giảng viên: {m.note}</p>}

      {m.submittable && (
        <>
          <p>
            <strong>Minh chứng</strong>
          </p>
          {evidence.length === 0 && <Empty>Chưa có minh chứng.</Empty>}
          {evidence.map((e) => (
            <Row key={e.id}>
              {e.filename ? <DownloadDoc href={`/api/evidence/${e.id}/download`} name={e.title || e.filename} /> : <span>{e.title}</span>}
              <StatusBadge kind="milestone" value={e.status} />
              {e.reviewer_comment && <span>— {e.reviewer_comment}</span>}
            </Row>
          ))}
          <ErrorText message={up.error ?? submit.error} />
          {working && !locked && (
            <Row>
              <FilePicker label="Tải minh chứng" accept=".pdf,.png,.jpg,.jpeg,.docx" disabled={up.busy} onFile={(file) => void up.run(() => upload(`/api/student/milestones/${m.code}/evidence`, file))} />
              <Button variant="primary" disabled={submit.busy || evidence.filter((e) => e.status !== "rejected").length === 0} onClick={() => void submit.run(() => send("POST", `/api/student/milestones/${m.code}/submit`))}>
                Nộp mốc
              </Button>
            </Row>
          )}
        </>
      )}

      {working && m.stored_status !== "accepted" && m.stored_status !== "submitted" && (
        <>
          <Button onClick={() => setExtending((v) => !v)}>{extending ? "Đóng" : "Xin gia hạn mốc này"}</Button>
          {extending && <ExtensionForm milestone={m} onDone={() => { setExtending(false); reload(); }} />}
        </>
      )}
    </Card>
  );
}

function ExtensionForm({ milestone, onDone }: { milestone: Milestone; onDone: () => void }) {
  const [due, setDue] = useState("");
  const [reason, setReason] = useState("");
  const action = useAction(onDone);
  return (
    <div style={{ marginTop: "0.75rem" }}>
      <Field label="Hạn mới đề nghị">
        <input type="date" value={due} min={milestone.due_date} onChange={(e) => setDue(e.target.value)} />
      </Field>
      <Field label="Lý do">
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <ErrorText message={action.error} />
      <Button variant="primary" disabled={action.busy || !due || !reason.trim()} onClick={() => void action.run(() => send("POST", "/api/student/requests/extension", { milestone_code: milestone.code, new_due_date: due, reason }))}>
        Gửi yêu cầu gia hạn
      </Button>
    </div>
  );
}
