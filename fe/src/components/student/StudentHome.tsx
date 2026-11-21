"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import { journey } from "@/lib/journey";
import { fmtDate } from "@/lib/labels";
import type { InternshipDetail } from "@/lib/types";
import { Async, Card, Cols, Empty, LinkButton, Page, Stepper, StatusBadge, Table } from "@/components/ui/ui";

// Việc chính theo trạng thái hồ sơ: nút nổi bật duy nhất trên trang.
const NEXT_STEP: Record<string, { text: string; action: string; href: string }> = {
  draft: { text: "Hoàn thiện và nộp hồ sơ thực tập", action: "Hoàn thiện hồ sơ", href: "/student/internship" },
  revision_requested: { text: "Giảng viên yêu cầu sửa hồ sơ: xem lý do và nộp lại", action: "Sửa và nộp lại", href: "/student/internship" },
  submitted: { text: "Hồ sơ đang chờ giảng viên xác nhận", action: "Xem hồ sơ", href: "/student/internship" },
  confirmed: { text: "Nộp đề cương thực tập", action: "Nộp đề cương", href: "/student/outline" },
  in_progress: { text: "Nộp nhật ký tuần, minh chứng theo mốc", action: "Đến mốc & minh chứng", href: "/student/milestones" },
  pending_credit: { text: "Chờ giảng viên thẩm định điều kiện công nhận tín chỉ", action: "Xem kết quả", href: "/student/final" },
  credit_review: { text: "Chờ quản trị viên phê duyệt công nhận tín chỉ", action: "Xem kết quả", href: "/student/final" },
  completed: { text: "Hoàn thành thực tập", action: "Xem kết quả", href: "/student/final" },
  closed_no_credit: { text: "Đợt thực tập đã kết thúc, không được công nhận", action: "Xem kết quả", href: "/student/final" },
  rejected: { text: "Hồ sơ bị từ chối", action: "Xem lý do", href: "/student/internship" },
};

// Trạng thái đang chờ người khác: không cần sinh viên làm gì thêm.
const WAITING = new Set(["submitted", "pending_credit", "credit_review"]);

export default function StudentHome() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Tổng quan thực tập của tôi">
      <Async state={state}>
        {(d) => {
          const row = d.internship;
          if (!row) {
            return (
              <>
                <Card>
                  <Stepper steps={journey(null)} />
                </Card>
                <Card title="Bắt đầu thực tập">
                  <p className="mb-4 mt-0 text-sm text-muted">Bạn chưa có hồ sơ thực tập. Khai báo hồ sơ để giảng viên xác nhận.</p>
                  <LinkButton href="/student/internship">Khai báo hồ sơ thực tập</LinkButton>
                </Card>
              </>
            );
          }
          const step = NEXT_STEP[row.status];
          const upcoming = d.milestones.filter((m) => m.status !== "accepted");
          const todo = upcoming.filter((m) => ["pending", "rejected", "overdue"].includes(m.status) && m.submittable).slice(0, 3);
          return (
            <>
              <Card>
                <Stepper steps={journey(row.status)} />
              </Card>
              <Card title="Việc cần làm">
                <p className="mb-3 mt-0 flex flex-wrap items-center gap-2 text-sm">
                  <StatusBadge kind="internship" value={row.status} />
                  <span className="text-muted">
                    Khóa {row.cohort} · Giảng viên: {row.lecturer_name ?? "chưa phân công"} · {fmtDate(row.start_date)} → {fmtDate(row.end_date)} · {row.company_name || "chưa khai báo doanh nghiệp"}
                  </span>
                </p>
                {row.decision_reason && (
                  <p className="mb-3 mt-0 rounded-lg bg-orange-50 px-3 py-2 text-sm text-orange-900 ring-1 ring-inset ring-orange-600/20 dark:bg-orange-950 dark:text-orange-200">
                    Lý do từ giảng viên: {row.decision_reason}
                  </p>
                )}
                {step && (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-bg px-4 py-3">
                    <span className="text-sm font-medium">{step.text}</span>
                    <LinkButton href={step.href} variant={WAITING.has(row.status) ? "default" : "primary"}>
                      {step.action}
                    </LinkButton>
                  </div>
                )}
                {todo.length > 0 && (
                  <ul className="m-0 mt-3 list-none space-y-2 p-0">
                    {todo.map((m) => (
                      <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-bg px-4 py-2.5 text-sm">
                        <span>
                          <StatusBadge kind="milestone" value={m.status} /> <span className="ml-1">{m.next_action}</span>
                        </span>
                        <Link href="/student/milestones" className="font-medium text-blue-600 hover:underline">
                          Mở mốc {m.code}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Cols>
                <Card title="Mốc cần làm">
                  {upcoming.length === 0 ? (
                    <Empty>Tất cả mốc đã hoàn tất.</Empty>
                  ) : (
                    <Table head={["Mốc", "Hạn", "Trạng thái"]}>
                      {upcoming.map((m) => (
                        <tr key={m.id}>
                          <td>{m.name}</td>
                          <td className="whitespace-nowrap">{fmtDate(m.due_date)}</td>
                          <td>
                            <StatusBadge kind="milestone" value={m.status} />
                          </td>
                        </tr>
                      ))}
                    </Table>
                  )}
                </Card>
                <Card title="Yêu cầu của tôi">
                  {d.requests.length === 0 ? (
                    <Empty>Chưa có yêu cầu gia hạn / ngoại lệ.</Empty>
                  ) : (
                    <ul className="m-0 mb-3 list-none space-y-2 p-0">
                      {d.requests.slice(0, 5).map((r) => (
                        <li key={r.id} className="flex items-center gap-2 text-sm">
                          <StatusBadge kind="request" value={r.status} /> {r.kind === "milestone_extension" ? `Gia hạn ${r.milestone_code ?? "mốc"}` : r.exception_type_name}
                        </li>
                      ))}
                    </ul>
                  )}
                  <Link href="/student/requests" className="text-sm font-medium text-blue-600 hover:underline">
                    Xem tất cả yêu cầu
                  </Link>
                </Card>
              </Cols>
            </>
          );
        }}
      </Async>
    </Page>
  );
}
