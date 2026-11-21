import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { SEVERITY, STATUS } from "../../lib/config";
import { Async, Badge, Card, CardHead, Empty, PageHead } from "../../components/ui";

// Dashboard chất lượng thực tập toàn khóa (GV/QTV). Chỉ đọc; số liệu do máy chủ tổng hợp theo phạm vi người xem
// (GV: sinh viên được phân công; QTV: toàn bộ). Biểu đồ vẽ bằng CSS — mỗi thanh đều có nhãn và con số, không chỉ dựa vào màu.

export const FLAG_LABEL = {
  overdue: "Mốc quá hạn", due_soon: "Sắp đến hạn", missing_evidence: "Thiếu minh chứng",
  low_hours: "Thiếu giờ thực tập", log_missing: "Thiếu nhật ký tuần",
};
export const KIND_LABEL = { late_extension: "Gia hạn quá hạn", credit_recognition: "Công nhận tín chỉ" };
const MS_PARTS = [
  ["accepted", "Đã chấp nhận", "var(--ok)"], ["submitted", "Chờ duyệt", "var(--info)"], ["pending", "Chưa nộp", "var(--line-strong)"],
  ["overdue", "Quá hạn", "var(--bad)"], ["rejected", "Bị trả lại", "var(--warn)"],
];

const pct = (v) => (v == null ? "—" : `${v}%`);
const days = (v) => (v == null ? "—" : `${v} ngày`);

export default function Dashboard() {
  const state = useAsync(() => api("GET", "/dashboard"));
  const { me } = useAuth();
  return (
    <Async state={state}>
      {(d) => (
        <>
          <PageHead title="Thống kê thực tập"
            subtitle={`${me.role === "admin" ? "Toàn khóa" : "Sinh viên bạn phụ trách"} · số liệu tính đến ${d.as_of.split("-").reverse().join("/")}`} />
          {d.kpis.internships === 0 ? <Empty>Chưa có hồ sơ thực tập nào để thống kê.</Empty> : <Body d={d} />}
        </>
      )}
    </Async>
  );
}

function Body({ d }) {
  return (
    <>
      <Kpis k={d.kpis} />
      <div className="dash-grid">
        <StatusChart rows={d.internship_status} />
        <MilestoneChart rows={d.milestones} />
        <RiskPanel risk={d.risk} />
        <RequestsPanel req={d.requests} />
        <LogsPanel logs={d.logs} />
        <Lecturers rows={d.lecturers} />
        <Programs rows={d.programs} />
      </div>
    </>
  );
}

function Kpis({ k }) {
  const items = [
    ["Tổng hồ sơ", k.internships], ["Đang thực tập", k.in_progress], ["Hoàn thành", k.completed],
    ["Mốc đã hoàn thành", pct(k.milestone_completion_pct)], ["Hồ sơ có cảnh báo", k.flagged_internships, k.flagged_internships ? "warn" : ""],
    ["Hồ sơ có mốc quá hạn", k.overdue_internships, k.overdue_internships ? "bad" : ""],
  ];
  return (
    <div className="kpis" role="list" aria-label="Chỉ số chính">
      {items.map(([label, value, tone]) => (
        <div key={label} className={`kpi ${tone || ""}`} role="listitem">
          <div className="kpi__value">{value}</div>
          <div className="kpi__label">{label}</div>
        </div>
      ))}
    </div>
  );
}

/** Danh sách thanh ngang: nhãn · thanh · số lượng. */
function Bars({ rows, label, max = Math.max(1, ...rows.map((r) => r.count)), color = "var(--primary)" }) {
  return (
    <div className="bars">
      {rows.map((r) => (
        <div key={label(r)} className="bar-row">
          <span className="bar-row__label">{label(r)}</span>
          <span className="bar-row__track"><span className="bar-row__fill" style={{ width: `${(100 * r.count) / max}%`, background: r.color || color }} /></span>
          <b className="bar-row__n">{r.count}</b>
        </div>
      ))}
    </div>
  );
}

function StatusChart({ rows }) {
  const shown = rows.filter((r) => r.count > 0);
  return (
    <Card>
      <CardHead title="Hồ sơ theo trạng thái" />
      {shown.length ? <Bars rows={shown} label={(r) => STATUS[r.status]?.[0] ?? r.status} /> : <p className="muted">Chưa có dữ liệu.</p>}
    </Card>
  );
}

function MilestoneChart({ rows }) {
  return (
    <Card className="dash-wide">
      <CardHead title="Tiến độ theo mốc" />
      {rows.length === 0 ? <p className="muted">Chưa có hồ sơ nào được duyệt để sinh mốc.</p> : (
        <>
          <div className="legend" aria-hidden="true">
            {MS_PARTS.map(([key, text, color]) => <span key={key}><i style={{ background: color }} />{text}</span>)}
          </div>
          {rows.map((m) => (
            <div key={m.code} className="stack-row">
              <div className="stack-row__head"><b>{m.name}</b><span className="muted small">{pct(m.accepted_pct)} đã chấp nhận · {m.total} hồ sơ</span></div>
              <div className="stack" role="img"
                aria-label={MS_PARTS.map(([key, text]) => `${text}: ${m[key]}`).join(", ")}>
                {MS_PARTS.map(([key, text, color]) => m[key] > 0 && (
                  <span key={key} title={`${text}: ${m[key]}`} style={{ flex: m[key], background: color }}>{m[key]}</span>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </Card>
  );
}

function RiskPanel({ risk }) {
  return (
    <Card className="dash-wide">
      <CardHead title="Rủi ro & cảnh báo" />
      {risk.open_flags === 0 ? <p className="muted">Không có cảnh báo nào đang mở.</p> : (
        <div className="dash-cols">
          <div>
            <h3 className="dash-h">Theo mức độ</h3>
            <Bars rows={risk.by_severity.filter((s) => s.count > 0)} label={(r) => SEVERITY[r.severity]?.[0] ?? r.severity}
              max={Math.max(1, ...risk.by_severity.map((s) => s.count))} />
            <h3 className="dash-h">Theo loại</h3>
            <Bars rows={risk.by_type} label={(r) => FLAG_LABEL[r.type] ?? r.type} />
          </div>
          <div>
            <h3 className="dash-h">Sinh viên rủi ro cao nhất</h3>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Sinh viên</th><th>Mức cao nhất</th><th>Cảnh báo mở</th></tr></thead>
                <tbody>
                  {risk.at_risk_students.map((s) => (
                    <tr key={s.internship_id}>
                      <td><Link to={`/internship/${s.internship_id}`}>{s.student}</Link>{s.top_reason && <div className="small muted">{s.top_reason}</div>}</td>
                      <td><Badge map={SEVERITY} status={s.max_severity} /></td>
                      <td>{s.open_flags}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function RequestRow({ label, s }) {
  return (
    <tr><th scope="row">{label}</th><td>{s.total}</td><td>{s.open}</td><td>{s.approved}</td><td>{s.rejected}</td><td>{days(s.avg_decision_days)}</td></tr>
  );
}

function RequestsPanel({ req }) {
  return (
    <Card>
      <CardHead title="Gia hạn & ngoại lệ" />
      <div className="table-wrap">
        <table>
          <thead><tr><th /><th>Tổng</th><th>Chờ</th><th>Duyệt</th><th>Từ chối</th><th>TB xử lý</th></tr></thead>
          <tbody>
            <RequestRow label="Gia hạn mốc" s={req.extensions} />
            <RequestRow label="Ngoại lệ" s={req.exceptions} />
          </tbody>
        </table>
      </div>
      {req.exceptions_by_kind.length > 0 && (
        <>
          <h3 className="dash-h">Ngoại lệ theo loại</h3>
          <Bars rows={req.exceptions_by_kind} label={(r) => KIND_LABEL[r.kind] ?? r.kind} />
        </>
      )}
    </Card>
  );
}

function LogsPanel({ logs }) {
  return (
    <Card>
      <CardHead title="Nhật ký thực tập" />
      <dl className="kv">
        <dt>Tổng số nhật ký</dt><dd>{logs.total}</dd>
        <dt>Đã chấp nhận</dt><dd>{logs.accepted} ({pct(logs.accepted_pct)} trong số đã duyệt)</dd>
        <dt>Bị trả lại</dt><dd>{logs.returned}</dd>
        <dt>Chờ duyệt</dt><dd>{logs.pending}</dd>
        <dt>Giờ TB mỗi tuần</dt><dd>{logs.avg_hours_per_week ?? "—"}</dd>
      </dl>
    </Card>
  );
}

function Lecturers({ rows }) {
  if (!rows.length) return null;
  return (
    <Card>
      <CardHead title="Tải công việc giảng viên" />
      <div className="table-wrap">
        <table>
          <thead><tr><th>Giảng viên</th><th>Sinh viên</th><th>Mục chờ duyệt</th><th>Cảnh báo mở</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.lecturer_id}><td>{r.name}</td><td>{r.students}</td><td>{r.pending_reviews}</td><td>{r.open_flags}</td></tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}

function Programs({ rows }) {
  if (!rows.length) return null;
  return (
    <Card>
      <CardHead title="Theo ngành" />
      <div className="table-wrap">
        <table>
          <thead><tr><th>Ngành</th><th>Hồ sơ</th><th>Hoàn thành</th><th>% mốc xong</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.program}><td>{r.program}</td><td>{r.internships}</td><td>{r.completed}</td><td>{pct(r.milestone_pct)}</td></tr>)}</tbody>
        </table>
      </div>
    </Card>
  );
}
