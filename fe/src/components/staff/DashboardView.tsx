"use client";

import { AlarmClock, Download, FolderOpen, Flag } from "lucide-react";
import { useApi } from "@/lib/hooks";
import { INTERNSHIP_STATUS, MILESTONE_STATUS } from "@/lib/labels";
import type { Dashboard } from "@/lib/types";
import { Async, Card, Cols, Empty, Page, ProgressBar, Row, StatCard, Table } from "@/components/ui/ui";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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
        <a href="/api/dashboard/export.csv" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-9 px-3.5 shadow-xs")}>
          <Download className="size-4" aria-hidden="true" />
          Xuất báo cáo (CSV)
        </a>
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
                <StatCard label="Tổng số hồ sơ" value={total} icon={FolderOpen} />
                <StatCard
                  label="Tỷ lệ trễ hạn"
                  value={`${lateRate}%`}
                  hint={`${d.late_internships}/${d.active_internships} hồ sơ đang thực tập có mốc quá hạn`}
                  icon={AlarmClock}
                  tone={lateRate > 0 ? "bad" : "good"}
                />
                <StatCard
                  label="Cờ rủi ro đang mở"
                  value={flagTotal}
                  hint={openFlags.map((f) => `${f.severity}: ${f.n}`).join(" · ") || "Không có"}
                  icon={Flag}
                  tone={flagTotal > 0 ? "warn" : "good"}
                />
              </div>
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
