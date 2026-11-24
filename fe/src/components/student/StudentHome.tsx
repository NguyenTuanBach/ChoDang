"use client";

import { useState, type ReactNode } from "react";
import { Async, Card, EmptyState, LinkButton, Page, StatCard, StatusBadge, Stepper } from "@/components/ui/ui";
import { useApi } from "@/lib/hooks";
import { journey } from "@/lib/journey";
import { fmtDate } from "@/lib/labels";
import type { InternshipDetail } from "@/lib/types";
import { useCurrentUser } from "@/lib/user-context";
import { cn } from "@/lib/utils";

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

const DAY_MS = 86_400_000;

const isoDate = (ms: number) => new Date(ms).toISOString().slice(0, 10);

// Một dòng nhắc việc: nội dung bên trái, nút "Mở ..." bên phải.
function ReminderRow({ children, href, action, urgent }: { children: ReactNode; href: string; action: string; urgent?: boolean }) {
  return (
    <li className={cn("flex flex-wrap items-center justify-between gap-3 rounded-lg border-2 border-foreground/25 bg-background px-4 py-3 text-sm", urgent && "border-l-[6px] border-l-destructive")}>
      <span className="min-w-0 flex-1">{children}</span>
      <LinkButton href={href}>{action}</LinkButton>
    </li>
  );
}

export default function StudentHome() {
  const user = useCurrentUser();
  const state = useApi<InternshipDetail>("/api/student/internship");
  const [nowMs] = useState(() => Date.now());
  const firstName = user.full_name.replace(/\(.*?\)/g, "").trim().split(/\s+/).at(-1) || user.email;

  return (
    <Page title={`Xin chào, ${firstName}`} description="Tổng quan hành trình thực tập của bạn.">
      <Async state={state}>
        {(d) => {
          const row = d.internship;
          if (!row) {
            return (
              <>
                <Card title="Giai đoạn hiện tại">
                  <Stepper steps={journey(null)} />
                </Card>
                <Card title="Bắt đầu thực tập">
                  <EmptyState noIcon title="Bạn chưa có hồ sơ thực tập" action={<LinkButton href="/student/internship">Khai báo hồ sơ thực tập</LinkButton>}>
                    Khai báo hồ sơ (doanh nghiệp, thời gian, giấy tiếp nhận) để giảng viên xác nhận.
                  </EmptyState>
                </Card>
              </>
            );
          }
          const steps = journey(row.status);
          const stage = steps.find((st) => st.state === "current" || st.state === "failed") ?? steps[steps.length - 1];
          const step = NEXT_STEP[row.status];
          const upcoming = d.milestones.filter((m) => m.status !== "accepted");
          const accepted = d.milestones.length - upcoming.length;
          const todo = upcoming.filter((m) => ["pending", "rejected", "overdue"].includes(m.status) && m.submittable).slice(0, 3);
          const daysLeft = row.end_date ? Math.ceil((Date.parse(row.end_date) - nowMs) / DAY_MS) : null;
          const overdue = d.milestones.filter((m) => m.status === "overdue").length;

          // Nhắc nộp nhật ký: tuần hiện tại (tính từ ngày bắt đầu, mỗi tuần 7 ngày) chưa có nhật ký.
          const startMs = row.start_date ? Date.parse(row.start_date) : NaN;
          const endMs = row.end_date ? Date.parse(row.end_date) : Infinity;
          const weekStart = Number.isFinite(startMs) && nowMs >= startMs && nowMs <= endMs + DAY_MS ? isoDate(startMs + Math.floor((nowMs - startMs) / (7 * DAY_MS)) * 7 * DAY_MS) : null;
          const journalDue = row.status === "in_progress" && weekStart !== null && !d.journals.some((j) => j.week_start === weekStart);
          const reminders = (journalDue ? 1 : 0) + todo.length;

          return (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard label="Thời gian còn lại" value={daysLeft === null ? "—" : daysLeft >= 0 ? `${daysLeft} ngày` : "Đã kết thúc"} hint={`Đến ${fmtDate(row.end_date)}`} />
                <StatCard label="Mốc hoàn tất" value={`${accepted}/${d.milestones.length}`} hint={overdue > 0 ? `${overdue} mốc quá hạn` : "Không có mốc quá hạn"} tone={overdue > 0 ? "bad" : "good"} href="/student/milestones" />
                <StatCard label="Minh chứng" value={d.evidence.length} hint="Tệp đã nộp theo mốc" href="/student/milestones" />
              </div>

              <Card title="Giai đoạn hiện tại">
                <Stepper steps={steps} />
                <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-foreground/15 pt-5">
                  <div className="min-w-0">
                    <p className="m-0 text-sm text-muted-foreground">Bạn đang ở bước</p>
                    <p className="m-0 text-lg font-semibold">{stage.label}</p>
                    {step && <p className="mb-0 mt-1 text-sm">Việc cần làm: {step.text}</p>}
                  </div>
                  {step && (
                    <LinkButton href={step.href} variant={WAITING.has(row.status) ? "default" : "primary"}>
                      {step.action}
                    </LinkButton>
                  )}
                </div>
                <div className="mt-5 border-t border-foreground/15 pt-5">
                  <p className="m-0 mb-3 text-sm font-medium">Các mốc thực tập</p>
                  {d.milestones.length === 0 ? (
                    <EmptyState noIcon>Chưa có mốc: mốc được tạo sau khi giảng viên xác nhận hồ sơ.</EmptyState>
                  ) : (
                    <ol className="m-0 list-none p-0">
                      {d.milestones.map((m, i) => (
                        <li key={m.id} className="relative flex gap-3 pb-4 last:pb-0">
                          {i < d.milestones.length - 1 && <span aria-hidden="true" className="absolute left-[7px] top-4 h-full w-px bg-border" />}
                          <span
                            aria-hidden="true"
                            className={cn(
                              "relative z-10 mt-1 size-4 shrink-0 rounded-full border-2",
                              m.status === "accepted" ? "border-success bg-success" : m.status === "overdue" ? "border-destructive bg-card" : "border-primary bg-card",
                            )}
                          />
                          <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-1">
                            <div className="min-w-0">
                              <p className="m-0 text-sm font-medium">{m.name}</p>
                              <p className="m-0 text-xs text-muted-foreground">Hạn {fmtDate(m.due_date)}</p>
                            </div>
                            <StatusBadge kind="milestone" value={m.status} />
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
                {row.decision_reason && (
                  <p className="mb-0 mt-4 rounded-lg bg-orange-50 px-3 py-2 text-sm text-orange-900 ring-1 ring-inset ring-orange-600/20 dark:bg-orange-950 dark:text-orange-200">
                    Lý do từ giảng viên: {row.decision_reason}
                  </p>
                )}
              </Card>

              <div className="grid grid-cols-1 items-stretch gap-5 md:grid-cols-2">
                <Card title="Thông tin thực tập">
                    <dl className="m-0 grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-2 text-sm">
                      <dt className="text-muted-foreground">Trạng thái</dt>
                      <dd className="m-0">
                        <StatusBadge kind="internship" value={row.status} />
                      </dd>
                      <dt className="text-muted-foreground">Khóa</dt>
                      <dd className="m-0">{row.cohort}</dd>
                      <dt className="text-muted-foreground">Giảng viên</dt>
                      <dd className="m-0">{row.lecturer_name ?? "Chưa phân công"}</dd>
                      <dt className="text-muted-foreground">Doanh nghiệp</dt>
                      <dd className="m-0">{row.company_name || "Chưa khai báo"}</dd>
                      <dt className="text-muted-foreground">Bắt đầu</dt>
                      <dd className="m-0">{fmtDate(row.start_date)}</dd>
                      <dt className="text-muted-foreground">Kết thúc</dt>
                      <dd className="m-0">{fmtDate(row.end_date)}</dd>
                    </dl>
                  </Card>
                <Card title="Yêu cầu của tôi">
                  <div className="flex h-full flex-col">
                    {d.requests.length === 0 ? (
                      <p className="m-0 text-sm text-muted-foreground">Bạn chưa gửi yêu cầu gia hạn hoặc ngoại lệ nào. Cần xin gia hạn mốc hay đổi thông tin thực tập thì gửi yêu cầu để giảng viên duyệt.</p>
                    ) : (
                      <ul className="m-0 list-none space-y-2 p-0">
                        {d.requests.slice(0, 4).map((r) => (
                          <li key={r.id} className="flex items-center justify-between gap-3 rounded-lg border-2 border-foreground/15 bg-background px-3 py-2 text-sm">
                            <span className="min-w-0 truncate">{r.kind === "milestone_extension" ? `Gia hạn ${r.milestone_code ?? "mốc"}` : r.exception_type_name}</span>
                            <StatusBadge kind="request" value={r.status} />
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="mt-auto flex flex-wrap gap-2 pt-4">
                      <LinkButton href="/student/requests">Gửi yêu cầu mới</LinkButton>
                      {d.requests.length > 0 && (
                        <LinkButton href="/student/requests" variant="default">
                          Xem tất cả
                        </LinkButton>
                      )}
                    </div>
                  </div>
                </Card>
              </div>

              {reminders > 0 && (
                <Card title="Nhắc việc">
                  <ul className="m-0 list-none space-y-3 p-0">
                    {journalDue && (
                      <ReminderRow href="/student/journal" action="Nộp nhật ký">
                        <strong>Nhật ký tuần này</strong> (từ {fmtDate(weekStart)}) chưa được nộp.
                      </ReminderRow>
                    )}
                    {todo.map((m) => (
                      <ReminderRow key={m.id} href="/student/milestones" action={`Mở mốc ${m.code}`} urgent={m.status === "overdue"}>
                        <StatusBadge kind="milestone" value={m.status} />
                        <p className="m-0 mt-1.5">
                          <strong>{m.name}</strong> — {m.next_action}
                        </p>
                      </ReminderRow>
                    ))}
                  </ul>
                </Card>
              )}
            </>
          );
        }}
      </Async>
    </Page>
  );
}
