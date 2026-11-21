"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import { fmtDate } from "@/lib/labels";
import type { InternshipDetail } from "@/lib/types";
import { Async, Card, Cols, Empty, Page, StatusBadge, Table } from "@/components/ui/ui";

const NEXT_STEP: Record<string, { text: string; href: string }> = {
  draft: { text: "Hoàn thiện và nộp hồ sơ thực tập", href: "/student/internship" },
  revision_requested: { text: "Giảng viên yêu cầu sửa hồ sơ: xem lý do và nộp lại", href: "/student/internship" },
  submitted: { text: "Hồ sơ đang chờ giảng viên xác nhận", href: "/student/internship" },
  confirmed: { text: "Nộp đề cương thực tập", href: "/student/outline" },
  in_progress: { text: "Nộp nhật ký tuần, minh chứng theo mốc", href: "/student/milestones" },
  pending_credit: { text: "Chờ giảng viên thẩm định điều kiện công nhận tín chỉ", href: "/student/final" },
  credit_review: { text: "Chờ quản trị viên phê duyệt công nhận tín chỉ", href: "/student/final" },
  completed: { text: "Hoàn thành thực tập", href: "/student/final" },
  closed_no_credit: { text: "Đợt thực tập đã kết thúc, không được công nhận", href: "/student/final" },
  rejected: { text: "Hồ sơ bị từ chối", href: "/student/internship" },
};

export default function StudentHome() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Tổng quan thực tập của tôi">
      <Async state={state}>
        {(d) => {
          const row = d.internship;
          if (!row) {
            return (
              <Card title="Bạn chưa có hồ sơ thực tập">
                <p>
                  <Link href="/student/internship">Khai báo hồ sơ thực tập</Link> để bắt đầu.
                </p>
              </Card>
            );
          }
          const step = NEXT_STEP[row.status];
          const upcoming = d.milestones.filter((m) => m.status !== "accepted");
          return (
            <>
              <Card title="Trạng thái">
                <p>
                  <StatusBadge kind="internship" value={row.status} /> Khóa {row.cohort} · Giảng viên: {row.lecturer_name ?? "chưa phân công"}
                </p>
                <p>
                  {fmtDate(row.start_date)} → {fmtDate(row.end_date)} · {row.company_name || "chưa khai báo doanh nghiệp"}
                </p>
                {row.decision_reason && <p>Lý do từ giảng viên: {row.decision_reason}</p>}
                {step && (
                  <p>
                    <strong>Việc cần làm tiếp:</strong> <Link href={step.href}>{step.text}</Link>
                  </p>
                )}
              </Card>
              <Cols>
                <Card title="Mốc cần làm">
                  {upcoming.length === 0 ? (
                    <Empty>Chưa có mốc nào cần làm.</Empty>
                  ) : (
                    <Table head={["Mốc", "Hạn", "Trạng thái", "Việc cần làm"]}>
                      {upcoming.map((m) => (
                        <tr key={m.id}>
                          <td>{m.name}</td>
                          <td>{fmtDate(m.due_date)}</td>
                          <td>
                            <StatusBadge kind="milestone" value={m.status} />
                          </td>
                          <td>{m.next_action}</td>
                        </tr>
                      ))}
                    </Table>
                  )}
                </Card>
                <Card title="Yêu cầu của tôi">
                  {d.requests.length === 0 ? (
                    <Empty>Chưa có yêu cầu gia hạn / ngoại lệ.</Empty>
                  ) : (
                    d.requests.slice(0, 5).map((r) => (
                      <p key={r.id}>
                        <StatusBadge kind="request" value={r.status} /> {r.kind === "milestone_extension" ? `Gia hạn ${r.milestone_code}` : r.exception_type_name}
                      </p>
                    ))
                  )}
                  <Link href="/student/requests">Xem tất cả</Link>
                </Card>
              </Cols>
            </>
          );
        }}
      </Async>
    </Page>
  );
}
