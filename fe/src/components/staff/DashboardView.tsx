"use client";

import { useApi } from "@/lib/hooks";
import { INTERNSHIP_STATUS, MILESTONE_STATUS } from "@/lib/labels";
import type { Dashboard } from "@/lib/types";
import { BarChart, BarLabels, CATEGORY_COLORS, PieChart } from "@/components/ui/charts";
import { Async, Card, Cols, DownloadButton, EmptyState, Page, ProgressBar, Row, StatCard, isDoneStatus } from "@/components/ui/ui";

const CREDIT_LABEL: Record<string, string> = {
  pending: "Đang thẩm định",
  lecturer_passed: "GV thẩm định đạt, chờ QTV",
  lecturer_returned: "GV trả lại",
  approved: "Được công nhận",
  denied: "Không công nhận",
};

// Rủi ro: cờ mới (chưa ghi nhận), cờ đang mở/đã ghi nhận theo mức độ, và hồ sơ trễ hạn.
function riskBars(d: Dashboard) {
  const active = d.flags.filter((f) => f.status === "open" || f.status === "acknowledged");
  const bySeverity = (sev: string) => active.filter((f) => f.severity === sev).reduce((n, f) => n + f.n, 0);
  return [
    { label: "Mới", value: d.flags.filter((f) => f.status === "open").reduce((n, f) => n + f.n, 0), color: "#2563eb" },
    { label: "Thông tin", value: bySeverity("info"), color: "#737373" },
    { label: "Cảnh báo", value: bySeverity("warning"), color: "#f59e0b" },
    { label: "Nghiêm trọng", value: bySeverity("critical"), color: "#dc2626" },
    { label: "Quá hạn", value: d.late_internships, color: "#ea580c" },
  ];
}

// Cột mốc: xanh lá = đã chấp nhận, đỏ = chưa hoàn thành / quá hạn / bị trả lại.
function milestoneBars(rows: { status: string; n: number }[]) {
  return rows.map((r) => ({ label: MILESTONE_STATUS[r.status] ?? r.status, value: r.n, color: isDoneStatus(r.status) ? "#16a34a" : "#dc2626" }));
}

function Bars({ rows, labels }: { rows: { key: string; n: number }[]; labels: Record<string, string> }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  if (rows.length === 0) return <EmptyState noIcon>Chưa có dữ liệu.</EmptyState>;
  return (
    <>
      {rows.map((r) => (
        <div key={r.key} className="mb-3 last:mb-0">
          <Row>
            <span>{labels[r.key] ?? r.key}</span>
            <strong>{r.n}</strong>
          </Row>
          <ProgressBar value={r.n} max={max} status={r.key} />
        </div>
      ))}
    </>
  );
}

// Số liệu toàn khóa (QTV) hoặc trong phạm vi mình phụ trách (GV): tiến độ, tỷ lệ trễ hạn, rủi ro, thời gian ra quyết định, công nhận (D7, D8).
export default function DashboardView() {
  const state = useApi<Dashboard>("/api/dashboard");
  return (
    <Page
      title="Dashboard"
      description="Tiến độ, trễ hạn, rủi ro và công nhận tín chỉ."
      actions={
        <DownloadButton href="/api/dashboard/export.csv">Xuất báo cáo (CSV)</DownloadButton>
      }
    >
      <Async state={state}>
        {(d) => {
          const total = d.internships_by_status.reduce((s, r) => s + r.n, 0);
          const lateRate = d.active_internships ? Math.round((d.late_internships / d.active_internships) * 100) : 0;
          const openFlags = d.flags.filter((f) => f.status === "open" || f.status === "acknowledged");
          const flagTotal = openFlags.reduce((s, f) => s + f.n, 0);
          return (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard label="Tổng số hồ sơ" value={total} />
                <StatCard
                  label="Tỷ lệ trễ hạn"
                  value={`${lateRate}%`}
                  hint={`${d.late_internships}/${d.active_internships} hồ sơ đang thực tập có mốc quá hạn`}
                 
                  tone={lateRate > 0 ? "bad" : "good"}
                />
                <StatCard
                  label="Cờ rủi ro đang mở"
                  value={flagTotal}
                  hint={openFlags.map((f) => `${f.severity}: ${f.n}`).join(" · ") || "Không có"}
                 
                  tone={flagTotal > 0 ? "warn" : "good"}
                />
              </div>
              <Cols>
                <Card title="Hồ sơ theo trạng thái">
                  <PieChart data={d.internships_by_status.map((r, i) => ({ label: INTERNSHIP_STATUS[r.status] ?? r.status, value: r.n, color: CATEGORY_COLORS[i % CATEGORY_COLORS.length] }))} />
                </Card>
                <Card title="Mốc theo trạng thái">
                  <BarChart data={milestoneBars(d.milestones_by_status)} />
                  <BarLabels data={milestoneBars(d.milestones_by_status)} />
                </Card>
              </Cols>
              <Cols>
                <Card title="Rủi ro">
                  <BarChart data={riskBars(d)} />
                  <BarLabels data={riskBars(d)} />
                </Card>
                <Card title="Kết quả công nhận tín chỉ">
                  <Bars rows={d.credit_outcomes.map((r) => ({ key: r.status, n: r.n }))} labels={CREDIT_LABEL} />
                </Card>
              </Cols>
              {d.sync_jobs.length > 0 && (
                <Card title="Đồng bộ LMS">
                  {d.sync_jobs.map((s) => (
                    <p key={s.status} className="my-1 text-sm">
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
