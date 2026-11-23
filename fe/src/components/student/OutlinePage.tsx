"use client";

import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/labels";
import type { InternshipDetail } from "@/lib/types";
import { Async, Button, Card, Empty, ErrorText, Field, Page, Pre, StatusBadge } from "@/components/ui/ui";

export default function OutlinePage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Đề cương thực tập">
      <Async state={state}>{(d) => <Content detail={d} reload={state.reload} />}</Async>
    </Page>
  );
}

function Content({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const [content, setContent] = useState(detail.outlines[0]?.status === "revision_requested" ? detail.outlines[0].content : "");
  const [codes, setCodes] = useState<string[]>(detail.outlines[0]?.outcome_codes ?? []);
  const submit = useAction(reload);
  const row = detail.internship;
  const pending = detail.outlines.some((o) => o.status === "submitted");
  const canSubmit = row?.status === "confirmed" && !pending;
  const outcomes = detail.outcomes ?? [];
  // Lý do chưa nộp được (form vẫn hiện nhưng khóa): đề cương chỉ nộp khi giảng viên đã xác nhận hồ sơ và chưa có bản đang chờ duyệt.
  const blockedReason =
    row?.status === "draft" || row?.status === "submitted" || row?.status === "revision_requested"
      ? "Bạn nộp được đề cương sau khi giảng viên xác nhận hồ sơ."
      : pending
        ? "Đề cương đang chờ giảng viên duyệt."
        : "Đề cương không cần nộp thêm ở trạng thái hiện tại.";

  function toggle(code: string) {
    setCodes((current) => (current.includes(code) ? current.filter((c) => c !== code) : [...current, code]));
  }

  if (!row) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;

  return (
    <>
      <Card title={detail.outlines.length ? "Nộp phiên bản mới" : "Nộp đề cương"}>
        {!canSubmit && <p className="mt-0 rounded-lg border-2 border-foreground/25 bg-background px-3 py-2 text-sm">{blockedReason}</p>}
        <Field label="Nội dung đề cương (mục tiêu, nhiệm vụ, kế hoạch, kết quả dự kiến)" required hint="Tối thiểu 50 ký tự. Nội dung đã nộp không sửa tại chỗ; sửa = nộp phiên bản mới.">
          <textarea value={content} disabled={!canSubmit} onChange={(e) => setContent(e.target.value)} style={{ minHeight: "12rem" }} />
        </Field>
        <p>
          <strong>Đối chiếu chuẩn đầu ra của khóa {row.cohort}:</strong>
        </p>
        {outcomes.length === 0 && <Empty>Quản trị viên chưa khai báo chuẩn đầu ra cho khóa này.</Empty>}
        {outcomes.map((o) => (
          <label key={o.id} style={{ display: "block", marginBottom: "0.25rem" }}>
            <input type="checkbox" disabled={!canSubmit} checked={codes.includes(o.code)} onChange={() => toggle(o.code)} /> <strong>{o.code}</strong> — {o.description}
          </label>
        ))}
        <ErrorText message={submit.error} />
        <Button variant="primary" disabled={!canSubmit || submit.busy || content.trim().length < 50} onClick={() => void submit.run(() => send("POST", "/api/student/outlines", { content, outcome_codes: codes }))}>
          Nộp đề cương
        </Button>
      </Card>

      <Card title="Các phiên bản đã nộp">
        {detail.outlines.length === 0 && <Empty>Chưa nộp đề cương.</Empty>}
        {detail.outlines.map((o) => (
          <div key={o.id} style={{ marginBottom: "1rem" }}>
            <p>
              <strong>Phiên bản {o.version}</strong> <StatusBadge kind="outline" value={o.status} /> · nộp {fmtDateTime(o.submitted_at)}
            </p>
            <Pre>{o.content}</Pre>
            {o.outcome_codes.length > 0 && <p>Chuẩn đầu ra: {o.outcome_codes.join(", ")}</p>}
            {o.feedback && <p>Phản hồi của giảng viên: {o.feedback}</p>}
          </div>
        ))}
      </Card>
    </>
  );
}
