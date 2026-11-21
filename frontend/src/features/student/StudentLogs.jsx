import { useState } from "react";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api, formData } from "../../lib/api";
import { Alert, Async, Badge, Button, Card, CardHead, Citation, Empty, Field, PageHead } from "../../components/ui";
import { EvidenceLink } from "../shared/EvidenceLink";

// Nhật ký tuần của sinh viên.

async function loadLogs() {
  const list = await api("GET", "/internships");
  const internship = list[0];
  if (!internship || !["approved", "in_progress", "completed"].includes(internship.status)) return { internship: null };
  const [logs, missing] = await Promise.all([
    api("GET", `/internships/${internship.id}/logs`), api("GET", `/internships/${internship.id}/logs/missing`),
  ]);
  return { internship, logs, missing };
}

export default function StudentLogs() {
  const state = useAsync(loadLogs);
  return (
    <>
      <PageHead title="Nhật ký tuần" />
      <Async state={state}>
        {(d) => d.internship
          ? <LogsBody key={d.logs.length} internship={d.internship} logs={d.logs} missing={d.missing} reload={state.reload} />
          : <Empty>Nhật ký mở sau khi hồ sơ đăng ký được duyệt.</Empty>}
      </Async>
    </>
  );
}

function LogsBody({ internship: i, logs, missing, reload }) {
  const { run } = useToast();
  const total = logs.reduce((s, l) => s + l.hours, 0);
  // Còn tuần bị bỏ sót → điền sẵn tuần sớm nhất để SV ghi bù
  const next = missing.weeks[0] ?? (logs.length ? Math.max(...logs.map((l) => l.week_no)) + 1 : 1);
  const [form, setForm] = useState({ week_no: next, hours: "", content: "", difficulties: "" });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async () => {
    try {
      await run(() => api("POST", `/internships/${i.id}/logs`, { ...form, week_no: Number(form.week_no), hours: Number(form.hours) }), "Đã ghi nhật ký");
    } catch {
      return; // run() đã hiện lỗi trên toast; giữ nguyên nội dung đã nhập để sinh viên sửa
    }
    setForm({ week_no: next + 1, hours: "", content: "", difficulties: "" });
    reload();
  };
  const attach = async (logId, file) => {
    if (!file) return;
    try {
      await run(() => api("POST", `/logs/${logId}/attachments`, formData({ file }), true), "Đã đính kèm file");
    } catch {
      return;
    }
    reload();
  };
  const resend = async (l) => {
    const content = prompt("Nội dung nhật ký đã bổ sung:", l.content);
    if (!content) return;
    try {
      await run(() => api("PATCH", `/logs/${l.id}`, { week_no: l.week_no, content, difficulties: l.difficulties, hours: l.hours }), "Đã gửi lại");
    } catch {
      return;
    }
    reload();
  };

  return (
    <>
      <p className="muted" style={{ marginTop: -12 }}>
        Tổng {total} giờ · quy chế: trung bình {i.mode === "part_time" ? 16 : 32} giờ/tuần (QĐ-TT/2026 · Điều 8 / Khoản 2)
      </p>

      {missing.weeks.length > 0 && (
        <Alert title={`Bạn chưa ghi nhật ký tuần ${missing.weeks.join(", ")}`}>
          <div>Quy chế yêu cầu ghi nhật ký hằng tuần. Ô "Tuần" bên dưới đã điền sẵn tuần {missing.weeks[0]} để bạn ghi bù.</div>
          <Citation c={missing.citation} />
        </Alert>
      )}

      {i.status !== "completed" && (
        <Card>
          <CardHead title="Ghi nhật ký mới" />
          <div className="grid2">
            <Field id="l-week" label="Tuần" type="number" min="1" value={form.week_no} onChange={set("week_no")} />
            <Field id="l-hours" label="Số giờ" type="number" min="0" max="80" step="0.5" value={form.hours} onChange={set("hours")} />
          </div>
          <div className="field-stack" style={{ marginTop: 16 }}>
            <Field id="l-content" as="textarea" label="Công việc đã làm" value={form.content} onChange={set("content")} />
            <Field id="l-diff" as="textarea" label="Khó khăn (nếu có)" style={{ minHeight: 64 }} value={form.difficulties} onChange={set("difficulties")} />
          </div>
          <div className="form-actions"><Button variant="primary" onClick={save}>Ghi nhật ký</Button></div>
        </Card>
      )}

      <Card>
        <CardHead title="Các tuần đã ghi" />
        <div className="table-wrap">
          <table>
            <thead><tr><th>Tuần</th><th>Nội dung</th><th>Giờ</th><th>Trạng thái</th></tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td>{l.week_no}</td>
                  <td>
                    <div className="pre">{l.content}</div>
                    {l.comment && <div className="small muted">GV: {l.comment}</div>}
                    {l.attachments.length > 0 && <div className="small">Đính kèm: {l.attachments.map((e) => <EvidenceLink key={e.id} id={e.id}>{e.filename}</EvidenceLink>)}</div>}
                    {l.review_status !== "accepted" && (
                      <label className="link-btn small" style={{ display: "inline-block", marginTop: 4 }}>
                        Đính kèm file <input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" hidden onChange={(e) => attach(l.id, e.target.files[0])} />
                      </label>
                    )}
                    {l.review_status === "returned" && <div><button className="link-btn" onClick={() => resend(l)}>Sửa & gửi lại</button></div>}
                  </td>
                  <td>{l.hours}</td>
                  <td><Badge status={l.review_status} /></td>
                </tr>
              ))}
              {logs.length === 0 && <tr><td colSpan="4" className="muted">Chưa có nhật ký.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
