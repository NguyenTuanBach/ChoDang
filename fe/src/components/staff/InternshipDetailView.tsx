"use client";

import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { FLAG_KIND, MODE_LABEL, fmtDate, fmtDateTime } from "@/lib/labels";
import type { InternshipDetail, Milestone, Outline, Suggestion } from "@/lib/types";
import { Async, Badge, Button, Card, Cols, DecisionPanel, Empty, ErrorText, Field, Page, Pre, Row, StatusBadge, Table } from "@/components/ui/ui";
import DownloadDoc from "@/components/student/DownloadDoc";
import { FlagActions } from "./FlagsPanel";
import { RequestDecision } from "./RequestsReview";

type Role = "lecturer" | "admin";

// Chi tiết một hồ sơ cho GV (xác nhận, duyệt, chấp nhận mốc, nhận xét, thẩm định) và QTV (xem, phê duyệt công nhận tín chỉ).
export default function InternshipDetailView({ id, role }: { id: number; role: Role }) {
  const state = useApi<InternshipDetail>(`/api/internships/${id}`);
  return (
    <Page title="Hồ sơ thực tập">
      <Async state={state}>{(d) => <Body d={d} role={role} reload={state.reload} />}</Async>
    </Page>
  );
}

type Pending = { kind: string; run: (reason: string) => Promise<unknown>; label: string; needReason: boolean; danger?: boolean } | null;

function Body({ d, role, reload }: { d: InternshipDetail; role: Role; reload: () => void }) {
  const row = d.internship;
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  if (!row) return <Empty>Không có dữ liệu.</Empty>;
  const isLecturer = role === "lecturer";
  const ask = (p: NonNullable<Pending>) => setPending(p);

  return (
    <>
      <Card>
        <Row>
          <h2 style={{ margin: 0 }}>{row.student_name}</h2>
          <StatusBadge kind="internship" value={row.status} />
          <span>
            {row.student_code ?? row.student_email} · Khóa {row.cohort} · GV: {row.lecturer_name ?? "—"}
          </span>
        </Row>
        <p>
          {row.company_name || "Chưa khai báo doanh nghiệp"} · {fmtDate(row.start_date)} → {fmtDate(row.end_date)} · {MODE_LABEL[row.mode]}
        </p>
        {row.decision_reason && <p>Lý do quyết định gần nhất: {row.decision_reason}</p>}
        {isLecturer && row.status === "submitted" && (
          <Row>
            <Button variant="primary" onClick={() => ask({ kind: "i", label: "Xác nhận hồ sơ", needReason: false, run: () => send("POST", `/api/internships/${row.id}/decision`, { action: "confirm" }) })}>
              Xác nhận hồ sơ
            </Button>
            <Button onClick={() => ask({ kind: "i", label: "Yêu cầu sửa", needReason: true, run: (reason) => send("POST", `/api/internships/${row.id}/decision`, { action: "request_revision", reason }) })}>
              Yêu cầu sửa
            </Button>
            <Button variant="danger" onClick={() => ask({ kind: "i", label: "Từ chối hồ sơ", needReason: true, danger: true, run: (reason) => send("POST", `/api/internships/${row.id}/decision`, { action: "reject", reason }) })}>
              Từ chối
            </Button>
          </Row>
        )}
        {pending?.kind === "i" && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
      </Card>

      <Cols>
        <Card title="Thông tin hồ sơ">
          <p>
            <strong>Doanh nghiệp:</strong> {row.company_name} (MST {row.company_tax_code})
            <br />
            {row.company_address}
          </p>
          <p>
            <strong>Vị trí:</strong> {row.position}
          </p>
          <p>
            <strong>Người hướng dẫn:</strong> {row.mentor_name} · {row.mentor_email} · {row.mentor_phone}
          </p>
          <p>
            <strong>Mô tả công việc:</strong>
          </p>
          <Pre>{row.job_description}</Pre>
          {Object.values(row.field_confirmations).includes("ai_confirmed") && <p><small>Các trường do AI gợi ý và sinh viên đã xác nhận: {Object.entries(row.field_confirmations).filter(([, v]) => v === "ai_confirmed").map(([k]) => k).join(", ")}</small></p>}
          {d.documents.map((doc) => (
            <div key={doc.id}>
              <DownloadDoc href={`/api/documents/${doc.id}/download`} name={doc.filename} />
            </div>
          ))}
        </Card>

        {d.credit && <CreditCard d={d} role={role} reload={reload} />}
      </Cols>

      <Card title="Đề cương">
        {d.outlines.length === 0 && <Empty>Chưa nộp đề cương.</Empty>}
        {d.outlines.map((o) => (
          <OutlineBlock key={o.id} outline={o} d={d} isLecturer={isLecturer} reload={reload} />
        ))}
      </Card>

      <Card title="Mốc">
        <Table head={["Mốc", "Hạn", "Trạng thái", "Minh chứng", ""]}>
          {d.milestones.map((m) => (
            <MilestoneRow key={m.id} m={m} d={d} isLecturer={isLecturer} reload={reload} />
          ))}
        </Table>
      </Card>

      <Card title="Nhật ký tuần">
        {d.journals.length === 0 && <Empty>Chưa có nhật ký.</Empty>}
        {d.journals.map((j) => (
          <JournalBlock key={j.id} j={j} isLecturer={isLecturer} reload={reload} />
        ))}
      </Card>

      <Card title="Yêu cầu gia hạn / ngoại lệ">
        {d.requests.length === 0 && <Empty>Không có yêu cầu.</Empty>}
        {d.requests.map((r) => {
          const mine = r.status === "open" && ((isLecturer && !r.affects_credit) || (!isLecturer && r.affects_credit));
          return (
            <div key={r.id} style={{ marginBottom: "0.75rem" }}>
              <Row>
                <StatusBadge kind="request" value={r.status} />
                <strong>{r.kind === "milestone_extension" ? `Gia hạn ${r.milestone_code} → ${fmtDate(r.new_due_date)}` : r.exception_type_name}</strong>
                {r.affects_credit && <Badge tone="warn">Ảnh hưởng tín chỉ</Badge>}
              </Row>
              <p>Lý do: {r.reason}</p>
              {r.decision_reason && <p>Phản hồi: {r.decision_reason}</p>}
              {r.attachments.map((a) => (
                <div key={a.id}>
                  <DownloadDoc href={`/api/request-attachments/${a.id}/download`} name={a.filename} />
                </div>
              ))}
              {mine && <RequestDecision item={r} reload={reload} />}
            </div>
          );
        })}
      </Card>

      <Card title="Cờ rủi ro">
        {d.flags.length === 0 && <Empty>Không có cờ.</Empty>}
        {d.flags.map((f) => (
          <div key={f.id} style={{ marginBottom: "0.75rem" }}>
            <Row>
              <StatusBadge kind="severity" value={f.severity} />
              <StatusBadge kind="flag" value={f.status} />
              <strong>{FLAG_KIND[f.kind] ?? f.kind}</strong>
              <Badge>{f.created_by_kind === "agent" ? "Do AI đề xuất" : "Do hệ thống phát hiện"}</Badge>
            </Row>
            <p>{f.reason}</p>
            {f.suggestion && <p>Gợi ý: {f.suggestion}</p>}
            <FlagActions flag={f} reload={reload} />
          </div>
        ))}
      </Card>
    </>
  );
}

function Decision({ pending, action, onCancel }: { pending: NonNullable<Pending>; action: ReturnType<typeof useAction>; onCancel: () => void }) {
  return (
    <DecisionPanel
      confirmLabel={pending.label}
      requireReason={pending.needReason}
      variant={pending.danger ? "danger" : "primary"}
      busy={action.busy}
      error={action.error}
      onCancel={onCancel}
      onSubmit={(reason) => void action.run(() => pending.run(reason))}
    />
  );
}

// Gợi ý của AI (tiền thẩm): luôn gắn nhãn, không có nút nào để AI quyết định thay giảng viên.
function Suggestions({ items }: { items: Suggestion[] }) {
  if (items.length === 0) return null;
  const s = items[0];
  return (
    <div style={{ borderLeft: "3px solid #b45309", paddingLeft: "0.75rem", margin: "0.5rem 0" }}>
      <Badge tone="warn">Gợi ý của AI — không thay quyết định của giảng viên</Badge> <small>{fmtDateTime(s.created_at)}</small>
      <Pre>{s.summary}</Pre>
      {s.details.outcome_matches && s.details.outcome_matches.length > 0 && (
        <ul>
          {s.details.outcome_matches.map((m) => (
            <li key={m.code}>
              {m.code}: {m.covered ? "có phủ" : "chưa thấy phủ"} — {m.note}
            </li>
          ))}
        </ul>
      )}
      {s.details.concerns && s.details.concerns.length > 0 && (
        <>
          <strong>Điểm cần lưu ý</strong>
          <ul>
            {s.details.concerns.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}
      {s.details.evidence_notes && s.details.evidence_notes.length > 0 && (
        <>
          <strong>Về minh chứng</strong>
          <ul>
            {s.details.evidence_notes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function PreReviewButton({ internshipId, kind, subjectId, reload }: { internshipId: number; kind: "outline" | "milestone"; subjectId: number; reload: () => void }) {
  const action = useAction(reload);
  return (
    <>
      <Button disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/internships/${internshipId}/pre-review`, { subject_kind: kind, subject_id: subjectId }))}>
        {action.busy ? "AI đang đọc..." : "Tiền thẩm bằng AI"}
      </Button>
      <ErrorText message={action.error} />
    </>
  );
}

function OutlineBlock({ outline: o, d, isLecturer, reload }: { outline: Outline; d: InternshipDetail; isLecturer: boolean; reload: () => void }) {
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  const suggestions = d.suggestions.filter((s) => s.subject_kind === "outline" && s.subject_id === o.id);
  const id = d.internship?.id ?? 0;
  return (
    <div style={{ marginBottom: "1rem" }}>
      <Row>
        <strong>Phiên bản {o.version}</strong>
        <StatusBadge kind="outline" value={o.status} />
        <span>{fmtDateTime(o.submitted_at)}</span>
      </Row>
      <Pre>{o.content}</Pre>
      {o.outcome_codes.length > 0 && <p>Chuẩn đầu ra đã khai: {o.outcome_codes.join(", ")}</p>}
      {o.feedback && <p>Phản hồi: {o.feedback}</p>}
      <Suggestions items={suggestions} />
      {o.status === "submitted" && (
        <Row>
          <PreReviewButton internshipId={id} kind="outline" subjectId={o.id} reload={reload} />
          {isLecturer && (
            <>
              <Button variant="primary" onClick={() => setPending({ kind: "o", label: "Duyệt đề cương", needReason: false, run: () => send("POST", `/api/outlines/${o.id}/decision`, { action: "approve" }) })}>
                Duyệt
              </Button>
              <Button onClick={() => setPending({ kind: "o", label: "Yêu cầu sửa", needReason: true, run: (reason) => send("POST", `/api/outlines/${o.id}/decision`, { action: "request_revision", reason }) })}>
                Yêu cầu sửa
              </Button>
              <Button variant="danger" onClick={() => setPending({ kind: "o", label: "Từ chối đề cương", needReason: true, danger: true, run: (reason) => send("POST", `/api/outlines/${o.id}/decision`, { action: "reject", reason }) })}>
                Từ chối
              </Button>
            </>
          )}
        </Row>
      )}
      {pending && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
    </div>
  );
}

function MilestoneRow({ m, d, isLecturer, reload }: { m: Milestone; d: InternshipDetail; isLecturer: boolean; reload: () => void }) {
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  const evidence = d.evidence.filter((e) => e.milestone_code === m.code);
  const suggestions = d.suggestions.filter((s) => s.subject_kind === "milestone" && s.subject_id === m.id);
  const id = d.internship?.id ?? 0;
  return (
    <>
      <tr>
        <td>
          {m.code} — {m.name}
        </td>
        <td>{fmtDate(m.due_date)}</td>
        <td>
          <StatusBadge kind="milestone" value={m.status} />
          {m.note && <div>{m.note}</div>}
        </td>
        <td>
          {evidence.length === 0 && "—"}
          {evidence.map((e) => (
            <div key={e.id}>{e.filename ? <DownloadDoc href={`/api/evidence/${e.id}/download`} name={e.title || e.filename} /> : e.title} <StatusBadge kind="milestone" value={e.status} /></div>
          ))}
        </td>
        <td>
          {m.stored_status === "submitted" && (
            <Row>
              <PreReviewButton internshipId={id} kind="milestone" subjectId={m.id} reload={reload} />
              {isLecturer && (
                <>
                  <Button variant="primary" onClick={() => setPending({ kind: "m", label: "Chấp nhận mốc", needReason: false, run: () => send("POST", `/api/milestones/${m.id}/accept`) })}>
                    Chấp nhận
                  </Button>
                  <Button variant="danger" onClick={() => setPending({ kind: "m", label: "Trả lại mốc", needReason: true, danger: true, run: (reason) => send("POST", `/api/milestones/${m.id}/reject`, { reason }) })}>
                    Trả lại
                  </Button>
                </>
              )}
            </Row>
          )}
        </td>
      </tr>
      {(pending || suggestions.length > 0) && (
        <tr>
          <td colSpan={5}>
            <Suggestions items={suggestions} />
            {pending && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
          </td>
        </tr>
      )}
    </>
  );
}

function JournalBlock({ j, isLecturer, reload }: { j: InternshipDetail["journals"][number]; isLecturer: boolean; reload: () => void }) {
  const [comment, setComment] = useState("");
  const action = useAction(() => {
    setComment("");
    reload();
  });
  return (
    <div style={{ marginBottom: "1rem" }}>
      <strong>Tuần bắt đầu {fmtDate(j.week_start)}</strong>
      <Pre>{j.content}</Pre>
      {j.lecturer_comment && <p>Nhận xét: {j.lecturer_comment}</p>}
      {isLecturer && (
        <>
          <Field label={j.lecturer_comment ? "Cập nhật nhận xét" : "Nhận xét"}>
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} style={{ minHeight: "3rem" }} />
          </Field>
          <ErrorText message={action.error} />
          <Button disabled={action.busy || !comment.trim()} onClick={() => void action.run(() => send("POST", `/api/journal/${j.id}/comment`, { comment }))}>
            Gửi nhận xét
          </Button>
        </>
      )}
    </div>
  );
}

function CreditCard({ d, role, reload }: { d: InternshipDetail; role: Role; reload: () => void }) {
  const row = d.internship;
  const credit = d.credit;
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  if (!row || !credit) return null;
  return (
    <Card title="Điều kiện công nhận tín chỉ (T1–T6)">
      <Table head={["Mã", "Điều kiện", "Hiện tại", "Ngưỡng", ""]}>
        {credit.items.map((i) => (
          <tr key={i.code}>
            <td>{i.code}</td>
            <td>{i.label}</td>
            <td>{i.value}</td>
            <td>{i.threshold}</td>
            <td>
              <Badge tone={i.met ? "good" : "warn"}>{i.met ? "Đạt" : "Chưa đạt"}</Badge>
            </td>
          </tr>
        ))}
      </Table>
      {credit.assessment && (
        <p>
          Thẩm định của giảng viên: <Badge>{credit.assessment.status}</Badge> {credit.assessment.lecturer_note}
          {credit.assessment.admin_reason && ` · QTV: ${credit.assessment.admin_reason}`}
        </p>
      )}
      {role === "lecturer" && row.status === "pending_credit" && (
        <Row>
          <Button variant="primary" disabled={!credit.all_met} onClick={() => setPending({ kind: "c", label: "Thẩm định đạt, chuyển QTV", needReason: false, run: (note) => send("POST", `/api/internships/${row.id}/credit/assess`, { passed: true, note }) })}>
            Thẩm định đạt
          </Button>
          <Button variant="danger" onClick={() => setPending({ kind: "c", label: "Trả hồ sơ lại cho sinh viên", needReason: true, danger: true, run: (note) => send("POST", `/api/internships/${row.id}/credit/assess`, { passed: false, note }) })}>
            Trả lại sinh viên
          </Button>
          {!credit.all_met && <small>Chỉ thẩm định đạt khi mọi điều kiện đạt (hãy chấp nhận mốc M3–M5 trước).</small>}
        </Row>
      )}
      {role === "admin" && row.status === "credit_review" && (
        <Row>
          <Button variant="primary" onClick={() => setPending({ kind: "c", label: "Phê duyệt công nhận (ghi LMS)", needReason: false, run: (reason) => send("POST", `/api/internships/${row.id}/credit/decision`, { approve: true, reason }) })}>
            Phê duyệt công nhận
          </Button>
          <Button variant="danger" onClick={() => setPending({ kind: "c", label: "Không công nhận", needReason: true, danger: true, run: (reason) => send("POST", `/api/internships/${row.id}/credit/decision`, { approve: false, reason }) })}>
            Không công nhận
          </Button>
        </Row>
      )}
      {pending && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
    </Card>
  );
}
