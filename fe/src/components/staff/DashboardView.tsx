"use client";

import { useApi } from "@/lib/hooks";
import { INTERNSHIP_STATUS, MILESTONE_STATUS } from "@/lib/labels";
import type { Dashboard } from "@/lib/types";
import { Async, Card, Cols, Empty, Page, ProgressBar, Row, Table } from "@/components/ui/ui";

const KIND_LABEL: Record<string, string> = { internship: "Hồ sơ", outline: "Đề cương", milestone: "Mốc", request: "Yêu cầu" };
const CREDIT_LABEL: Record<string, string> = {
  pending: "Đang thẩm định",
  lecturer_passed: "GV thẩm định đạt, chờ QTV",
  lecturer_returned: "GV trả lại",
  approved: "Được công nhận",
  denied: "Không công nhận",
};

function Bars({ rows, labels }: { rows: { key: string; n: number }[]; labels: Record<string, string> }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  if (rows.length === 0) return <Empty>Chưa có dữ liệu.</Empty>;
  return (
    <>
      {rows.map((r) => (
        <div key={r.key} style={{ marginBottom: "0.5rem" }}>
          <Row>
            <span>{labels[r.key] ?? r.key}</span>
            <strong>{r.n}</strong>
          </Row>
          <ProgressBar value={r.n} max={max} />
        </div>
      ))}
    </>
  );
}

// Số liệu toàn khóa (QTV) hoặc trong phạm vi mình phụ trách (GV): tiến độ, tỷ lệ trễ hạn, rủi ro, thời gian ra quyết định, công nhận (D7, D8).
export default function DashboardView() {
  const state = useApi<Dashboard>("/api/dashboard");
  return (
    <Page title="Dashboard" actions={<a href="/api/dashboard/export.csv">Xuất báo cáo (CSV)</a>}>
      <Async state={state}>
        {(d) => {
          const total = d.internships_by_status.reduce((s, r) => s + r.n, 0);
          const lateRate = d.active_internships ? Math.round((d.late_internships / d.active_internships) * 100) : 0;
          const openFlags = d.flags.filter((f) => f.status === "open" || f.status === "acknowledged");
          const flagTotal = openFlags.reduce((s, f) => s + f.n, 0);
          return (
            <>
              <Cols>
                <Card title="Tổng số hồ sơ">
                  <h2 style={{ fontSize: "2rem", margin: 0 }}>{total}</h2>
                </Card>
                <Card title="Tỷ lệ trễ hạn">
                  <h2 style={{ fontSize: "2rem", margin: 0 }}>{lateRate}%</h2>
                  <small>
                    {d.late_internships}/{d.active_internships} hồ sơ đang thực tập có mốc quá hạn
                  </small>
                </Card>
                <Card title="Cờ rủi ro đang mở">
                  <h2 style={{ fontSize: "2rem", margin: 0 }}>{flagTotal}</h2>
                  <small>{openFlags.map((f) => `${f.severity}: ${f.n}`).join(" · ") || "Không có"}</small>
                </Card>
              </Cols>
              <Cols>
                <Card title="Hồ sơ theo trạng thái">
                  <Bars rows={d.internships_by_status.map((r) => ({ key: r.status, n: r.n }))} labels={INTERNSHIP_STATUS} />
                </Card>
                <Card title="Mốc theo trạng thái">
                  <Bars rows={d.milestones_by_status.map((r) => ({ key: r.status, n: r.n }))} labels={MILESTONE_STATUS} />
                </Card>
              </Cols>
              <Cols>
                <Card title="Thời gian ra quyết định (trung vị)">
                  <Table head={["Loại", "Số quyết định", "Trung vị (ngày)"]}>
                    {d.decision_times.map((t) => (
                      <tr key={t.kind}>
                        <td>{KIND_LABEL[t.kind] ?? t.kind}</td>
                        <td>{t.count}</td>
                        <td>{t.median_days === null ? "—" : t.median_days.toFixed(1)}</td>
                      </tr>
                    ))}
                  </Table>
                </Card>
                <Card title="Kết quả công nhận tín chỉ">
                  <Bars rows={d.credit_outcomes.map((r) => ({ key: r.status, n: r.n }))} labels={CREDIT_LABEL} />
                </Card>
              </Cols>
              {d.sync_jobs.length > 0 && (
                <Card title="Đồng bộ LMS">
                  {d.sync_jobs.map((s) => (
                    <p key={s.status}>
                      {s.status}: {s.n}
                    </p>
                  ))}
                </Card>
              )}
            </>
          );
        }}
      </Async>
    </Page>
  );
}
