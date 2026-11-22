"use client";

import Link from "next/link";
import { useState } from "react";
import { query } from "@/lib/http";
import { useApi } from "@/lib/hooks";
import { INTERNSHIP_STATUS, MILESTONE_STATUS, fmtDate } from "@/lib/labels";
import type { ListRow } from "@/lib/types";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Async, Badge, Card, DownloadButton, Empty, Field, Page, Row, StatusBadge, Table } from "@/components/ui/ui";

// Danh sách tổng hợp có lọc theo trạng thái, mốc, rủi ro; xuất CSV (A11).
export default function InternshipList({ base, fixedStatus, title }: { base: "/lecturer" | "/admin"; fixedStatus?: string; title?: string }) {
  const [status, setStatus] = useState(fixedStatus ?? "");
  const [milestone, setMilestone] = useState("");
  const [milestoneStatus, setMilestoneStatus] = useState("");
  const [flagged, setFlagged] = useState(false);
  const qs = query({ status, milestone_code: milestone, milestone_status: milestone ? milestoneStatus : "", flagged });
  const state = useApi<ListRow[]>(`/api/internships${qs}`);

  return (
    <Page title={title ?? "Danh sách hồ sơ thực tập"} actions={<DownloadButton href={`/api/internships/export.csv${qs}`}>Xuất CSV</DownloadButton>}>
      <Card title="Bộ lọc">
        <Row>
          {!fixedStatus && (
            <Field label="Trạng thái hồ sơ">
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">Tất cả</option>
                {Object.entries(INTERNSHIP_STATUS).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Mốc">
            <select value={milestone} onChange={(e) => setMilestone(e.target.value)}>
              <option value="">Tất cả</option>
              {["M1", "M2", "M3", "M4", "M5"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Trạng thái mốc">
            <select value={milestoneStatus} disabled={!milestone} onChange={(e) => setMilestoneStatus(e.target.value)}>
              <option value="">Bất kỳ</option>
              {Object.entries(MILESTONE_STATUS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <label>
            <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} /> Chỉ hồ sơ có cờ rủi ro
          </label>
        </Row>
      </Card>
      <Card>
        <Async state={state}>
          {(rows) =>
            rows.length === 0 ? (
              <Empty>Không có hồ sơ phù hợp.</Empty>
            ) : (
              <Table head={["Sinh viên", "Doanh nghiệp", "GV", "Trạng thái", "Bắt đầu", "Kết thúc", "Quá hạn", "Chờ duyệt", ""]}>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {r.student_name}
                      <br />
                      <small>{r.student_code ?? r.student_email}</small>
                    </td>
                    <td>{r.company_name || "—"}</td>
                    <td>{r.lecturer_name ?? "—"}</td>
                    <td className="whitespace-nowrap">
                      <StatusBadge kind="internship" value={r.status} />
                    </td>
                    <td className="whitespace-nowrap">{fmtDate(r.start_date)}</td>
                    <td className="whitespace-nowrap">{fmtDate(r.end_date)}</td>
                    <td className="whitespace-nowrap text-center">{r.overdue_milestones > 0 ? <Badge tone="bad">{r.overdue_milestones}</Badge> : 0}</td>
                    <td className="whitespace-nowrap text-center">{r.submitted_milestones}</td>
                    <td className="whitespace-nowrap">
                      <Link href={`${base}/internships/${r.id}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "border-2 border-foreground/25 no-underline")}>
                        Mở
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>
            )
          }
        </Async>
      </Card>
    </Page>
  );
}
