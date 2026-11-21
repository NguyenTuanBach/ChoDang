import { useState } from "react";
import { Link } from "react-router-dom";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { FIELDS } from "../../lib/config";
import { fmtDate, fmtDateTime, storage } from "../../lib/format";
import { AiBox, AiTag, Alert, Async, Avatar, Badge, Card, Empty, PageHead } from "../../components/ui";
import { EvidenceLink } from "../shared/EvidenceLink";
import { ExceptionAi, KIND_LABEL, exceptionDetail } from "../student/ExceptionPanel";
import DecisionBox from "./DecisionBox";
import ReviewInline from "./ReviewInline";

// Hàng chờ phê duyệt của giảng viên: hồ sơ, đề cương, mốc đã nộp, nhật ký tuần, gia hạn.

const SECTIONS = [
  ["internships", "Hồ sơ đăng ký", (i, reload) => <InternshipCard key={`i${i.id}`} i={i} reload={reload} />],
  ["outlines", "Đề cương", (o, reload) => <OutlineCard key={`o${o.id}`} o={o} reload={reload} />],
  ["milestones", "Mốc đã nộp", (m, reload) => <MilestoneCard key={`m${m.id}`} m={m} reload={reload} />],
  ["exceptions", "Ngoại lệ", (e, reload) => <ExceptionCard key={`x${e.id}`} e={e} reload={reload} />],
  ["extensions", "Xin gia hạn", (e, reload) => <ExtensionCard key={`e${e.id}`} e={e} reload={reload} />],
  ["logs", "Nhật ký tuần", (l, reload) => <LogCard key={`l${l.id}`} l={l} reload={reload} />],
];

// Điểm ưu tiên do máy chủ tính theo luật (services/priority.py) — chỉ đổi THỨ TỰ hiển thị, GV vẫn tự quyết.
const MODES = [["priority", "Ưu tiên"], ["oldest", "Chờ lâu nhất"], ["type", "Theo loại"]];
const MODE_KEY = "vin15_queue_sort";
const since = (x) => (x.item.priority?.since ? Date.parse(x.item.priority.since + "Z") : Infinity);
const byOldest = (a, b) => since(a) - since(b);
const byPriority = (a, b) => (b.item.priority?.score ?? 0) - (a.item.priority?.score ?? 0) || byOldest(a, b);

export default function LecturerQueue() {
  const state = useAsync(() => api("GET", "/approvals/queue"));
  const [mode, setMode] = useState(() => (MODES.some(([m]) => m === storage("get", MODE_KEY)) ? storage("get", MODE_KEY) : "priority"));
  const choose = (m) => { setMode(m); storage("set", MODE_KEY, m); };
  return (
    <Async state={state}>
      {(q) => {
        const entries = SECTIONS.flatMap(([key, , render]) => (q[key] || []).map((item) => ({ key, item, render })));
        const show = (list) => list.map(({ item, render }) => render(item, state.reload));
        return (
          <>
            <PageHead title="Hàng chờ phê duyệt" subtitle={entries.length ? `${entries.length} mục đang chờ bạn xử lý` : undefined}>
              {entries.length > 1 && (
                <div className="src__tabs" role="group" aria-label="Sắp xếp hàng chờ">
                  {MODES.map(([m, label]) => (
                    <button key={m} type="button" className={mode === m ? "is-on" : ""} aria-pressed={mode === m} onClick={() => choose(m)}>{label}</button>
                  ))}
                </div>
              )}
            </PageHead>
            {entries.length === 0 && <Empty>Không có mục nào chờ duyệt.</Empty>}
            {mode === "type"
              ? SECTIONS.map(([key, label]) => {
                  const group = entries.filter((x) => x.key === key).sort(byPriority);
                  return group.length > 0 && (
                    <section key={key} aria-label={label}>
                      <h2 className="queue-section">{label} <span className="muted">({group.length})</span></h2>
                      {show(group)}
                    </section>
                  );
                })
              : show([...entries].sort(mode === "oldest" ? byOldest : byPriority))}
          </>
        );
      }}
    </Async>
  );
}

const LEVEL = { high: ["Ưu tiên cao", "bad"], medium: ["Ưu tiên vừa", "warn"] };

function PriorityLine({ p }) {
  const level = p && LEVEL[p.level];
  if (!p || (!level && !p.reasons.length)) return null;
  return (
    <div className="priority-line" aria-label="Lý do ưu tiên">
      {level && <span className={`badge ${level[1]}`}>{level[0]}</span>}
      {p.reasons.map((r) => <span key={r} className="badge">{r}</span>)}
    </div>
  );
}

function StudentLink({ id }) {
  return <Link className="small" to={`/internship/${id}`}>Xem hồ sơ →</Link>;
}

function EvidenceList({ items }) {
  if (!items.length) return <p className="small muted">Chưa có file minh chứng.</p>;
  return (
    <ul className="evidence-list">
      {items.map((e) => (
        <li key={e.id}><EvidenceLink id={e.id}>{e.filename}</EvidenceLink><span className="small muted">{fmtDateTime(e.uploaded_at)}</span></li>
      ))}
    </ul>
  );
}

function MilestoneCard({ m, reload }) {
  return (
    <Card data-priority={m.priority?.score}>
      <Header name={m.student.full_name} subtitle={`Mốc: ${m.name}`} right={<StudentLink id={m.internship_id} />} priority={m.priority} />
      <p className="small muted" style={{ margin: "12px 0" }}>
        Hạn {fmtDate(m.due_date)}{m.submitted_at && ` · nộp lúc ${fmtDateTime(m.submitted_at)}`}
      </p>
      {m.missing_evidence.length > 0 && <Alert title="Thiếu minh chứng bắt buộc">{m.missing_evidence.join(", ")}</Alert>}
      <EvidenceList items={m.evidence} />
      <ReviewInline path={`/milestones/${m.id}/review`} rejectDecision="rejected" onDone={reload} />
    </Card>
  );
}

function LogCard({ l, reload }) {
  return (
    <Card data-priority={l.priority?.score}>
      <Header name={l.student.full_name} subtitle={`Nhật ký tuần ${l.week_no} · ${l.hours} giờ`} right={<StudentLink id={l.internship_id} />} priority={l.priority} />
      <p className="pre" style={{ margin: "12px 0" }}>{l.content}</p>
      {l.difficulties && <p className="small muted">Khó khăn: {l.difficulties}</p>}
      {l.attachments.length > 0 && <EvidenceList items={l.attachments} />}
      <ReviewInline path={`/logs/${l.id}/review`} rejectDecision="returned" onDone={reload} />
    </Card>
  );
}

function Header({ name, subtitle, right, priority }) {
  return (
    <>
      <div className="row spread">
        <div className="who"><Avatar name={name} /><div><div style={{ fontWeight: 700, fontSize: "1.05rem" }}>{name}</div><div className="small muted">{subtitle}</div></div></div>
        {right}
      </div>
      <PriorityLine p={priority} />
    </>
  );
}

function fieldValue(i, n) {
  if (n.endsWith("date")) return fmtDate(i[n]);
  if (n === "mode") return i[n] === "part_time" ? "Bán thời gian" : "Toàn thời gian";
  return i[n] || "—";
}

function InternshipCard({ i, reload }) {
  const ai = new Set(i.ai_fields || []);
  return (
    <Card data-priority={i.priority?.score}>
      <Header name={i.student.full_name} subtitle="Hồ sơ đăng ký" right={<Badge status={i.status} />} priority={i.priority} />
      <dl className="kv">
        {FIELDS.map(([n, l]) => (
          <div key={n}><dt>{l} {ai.has(n) && <AiTag />}</dt><dd>{fieldValue(i, n)}</dd></div>
        ))}
      </dl>
      <DecisionBox kind="internship" id={i.id} version={i.version} onDone={reload} />
    </Card>
  );
}

export function OutlineAi({ s }) {
  if (!s) return <p className="muted small">Không có gợi ý AI cho đề cương này.</p>;
  return (
    <AiBox label={s.label}>
      <p>{s.summary}</p>
      {s.uncovered_outcomes.length ? (
        <>
          <p className="small"><b>Chuẩn đầu ra chưa thấy nhắc tới:</b></p>
          <ul className="small">{s.uncovered_outcomes.map((c) => <li key={c.code}>{c.code} — {c.text}</li>)}</ul>
        </>
      ) : <p className="small">Đề cương có nhắc tới mọi chuẩn đầu ra học phần.</p>}
    </AiBox>
  );
}

function OutlineCard({ o, reload }) {
  return (
    <Card data-priority={o.priority?.score}>
      <Header name={o.internship.student.full_name} subtitle={`Đề cương thực tập · phiên bản ${o.version}`} priority={o.priority} />
      <p className="pre" style={{ margin: "16px 0" }}>{o.content}</p>
      <OutlineAi s={o.ai_summary} />
      <DecisionBox kind="outline" id={o.id} version={o.version} onDone={reload} />
    </Card>
  );
}

function ExceptionCard({ e, reload }) {
  return (
    <Card data-priority={e.priority?.score}>
      <Header name={e.student.full_name} subtitle={`Ngoại lệ · ${KIND_LABEL[e.kind]}`}
        right={<div>{exceptionDetail(e)}</div>} priority={e.priority} />
      <p className="pre" style={{ margin: "16px 0" }}>{e.reason}</p>
      {e.evidence_id && <p className="small">Minh chứng kèm theo: <EvidenceLink id={e.evidence_id}>mở file</EvidenceLink></p>}
      <ExceptionAi summary={e.ai_summary} />
      <DecisionBox kind="exception" id={e.id} onDone={reload} />
    </Card>
  );
}

function ExtensionCard({ e, reload }) {
  return (
    <Card data-priority={e.priority?.score}>
      <Header name={e.student.full_name} subtitle={`Xin gia hạn · ${e.milestone.name}`}
        right={<div>{fmtDate(e.previous_due_date)} → <b>{fmtDate(e.requested_due_date)}</b></div>} priority={e.priority} />
      <p className="pre" style={{ margin: "16px 0" }}>{e.reason}</p>
      {e.evidence_id && <p className="small">Minh chứng kèm theo: <EvidenceLink id={e.evidence_id}>mở file</EvidenceLink></p>}
      {e.ai_summary && (
        <AiBox label={e.ai_summary.label}>
          <p>{e.ai_summary.summary}</p>
          {e.ai_summary.related_clauses.map((c, idx) => (
            <details key={idx}><summary className="small">{c.label}</summary><p className="pre small">{c.text}</p></details>
          ))}
        </AiBox>
      )}
      <DecisionBox kind="extension" id={e.id} onDone={reload} />
    </Card>
  );
}
