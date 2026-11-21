import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import { AiBox, Badge, Button, Card, CardHead, Field } from "../../components/ui";

// Yêu cầu ngoại lệ của sinh viên (gia hạn quá hạn, công nhận/quy đổi tín chỉ): gửi, theo dõi, hủy khi còn chờ.
// Quyết định luôn do giảng viên phụ trách (HITL) — màn này không có đường tự duyệt.

export const KIND_LABEL = { late_extension: "Gia hạn quá hạn", credit_recognition: "Công nhận / quy đổi tín chỉ" };

export function exceptionDetail(e) {
  if (e.kind === "late_extension") {
    return `${e.milestone?.name ?? "Mốc"}: ${fmtDate(e.payload.previous_due_date)} → ${fmtDate(e.payload.requested_due_date)}`;
  }
  return `Đề nghị công nhận ${e.payload.credits} tín chỉ${e.payload.basis ? ` · ${e.payload.basis}` : ""}`;
}

export default function ExceptionPanel({ internship, exceptions, reload }) {
  const { me } = useAuth();
  const { run } = useToast();
  const [form, setForm] = useState(null);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const lateMilestones = internship.milestones.filter((m) => m.status !== "accepted");
  const open = (kind) => setForm({ kind, reason: "", milestone_id: lateMilestones[0]?.id ?? "", date: "", credits: "", basis: "" });

  const submit = async () => {
    const body = { kind: form.kind, reason: form.reason };
    if (form.kind === "late_extension") {
      body.milestone_id = Number(form.milestone_id);
      body.payload = { requested_due_date: form.date };
    } else {
      body.payload = { credits: Number(form.credits), basis: form.basis };
    }
    try {
      await run(() => api("POST", `/internships/${internship.id}/exceptions`, body), "Đã gửi yêu cầu ngoại lệ");
    } catch {
      return; // run() đã hiện lỗi trên toast; giữ nguyên form để sửa
    }
    setForm(null);
    reload();
  };

  const cancel = async (id) => {
    try {
      await run(() => api("POST", `/exceptions/${id}/cancel`), "Đã hủy yêu cầu");
    } catch {
      return;
    }
    reload();
  };

  return (
    <Card>
      <CardHead title="Yêu cầu ngoại lệ">
        {me.role === "student" && !form && (
          <>
            <Button size="sm" onClick={() => open("late_extension")} disabled={!lateMilestones.length}>Gia hạn quá hạn</Button>{" "}
            <Button size="sm" onClick={() => open("credit_recognition")}>Công nhận tín chỉ</Button>
          </>
        )}
      </CardHead>
      <p className="small muted">Ngoại lệ do giảng viên phụ trách xem xét và quyết định; mọi bước đều được lưu vết.</p>

      {form && (
        <div className="form" aria-label="Gửi yêu cầu ngoại lệ">
          <h3>{KIND_LABEL[form.kind]}</h3>
          {form.kind === "late_extension" ? (
            <>
              <Field as="select" id="ex-milestone" label="Mốc cần gia hạn" value={form.milestone_id}
                onChange={(e) => set("milestone_id", e.target.value)}>
                {lateMilestones.map((m) => <option key={m.id} value={m.id}>{m.name} (hạn {fmtDate(m.due_date)})</option>)}
              </Field>
              <Field id="ex-date" type="date" label="Hạn mới đề nghị" value={form.date} onChange={(e) => set("date", e.target.value)} />
            </>
          ) : (
            <>
              <Field id="ex-credits" type="number" min="0" step="0.5" label="Số tín chỉ đề nghị công nhận" value={form.credits}
                onChange={(e) => set("credits", e.target.value)} />
              <Field id="ex-basis" label="Học phần / căn cứ quy đổi" value={form.basis} onChange={(e) => set("basis", e.target.value)} />
            </>
          )}
          <Field as="textarea" id="ex-reason" label="Lý do (tối thiểu 10 ký tự)" value={form.reason}
            onChange={(e) => set("reason", e.target.value)} style={{ minHeight: 72 }} />
          <div className="form-actions">
            <Button variant="primary" onClick={submit} disabled={form.reason.trim().length < 10}>Gửi yêu cầu</Button>
            <Button onClick={() => setForm(null)}>Đóng</Button>
          </div>
        </div>
      )}

      {exceptions.map((e) => (
        <div key={e.id} className="list-item row spread">
          <div>
            <b>{KIND_LABEL[e.kind]}</b> <Badge status={e.status} />
            <div className="small muted">{exceptionDetail(e)} · {e.reason}</div>
            {e.decision_reason && <div className="small">GV: {e.decision_reason}</div>}
          </div>
          {e.status === "open" && me.role === "student" && <Button size="sm" variant="danger" onClick={() => cancel(e.id)}>Hủy</Button>}
        </div>
      ))}
    </Card>
  );
}

/** Khối thông tin ngoại lệ dùng cho cả hàng chờ giảng viên. */
export function ExceptionAi({ summary }) {
  if (!summary) return null;
  return (
    <AiBox label={summary.label}>
      <p>{summary.summary}</p>
      {summary.related_clauses.map((c, idx) => (
        <details key={idx}><summary className="small">{c.label}</summary><p className="pre small">{c.text}</p></details>
      ))}
    </AiBox>
  );
}
