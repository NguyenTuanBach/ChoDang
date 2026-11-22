"use client";

import { ArrowRight, CalendarCheck, CalendarClock, ClipboardCheck, NotebookPen, Paperclip, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useAssistantContext } from "@/components/assistant/AssistantProvider";
import { Async, Card, Empty, EmptyState, LinkButton, Page, StatCard, StatusBadge, Stepper } from "@/components/ui/ui";
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

const ASK = ["Em còn thiếu gì để được công nhận tín chỉ?", "Hạn nộp đề cương là khi nào?", "Mở trang mốc và minh chứng giúp em"];

const DAY_MS = 86_400_000;

function weeksBetween(start: string | null, end: string | null): number {
  if (!start || !end) return 0;
  const days = (Date.parse(end) - Date.parse(start)) / DAY_MS;
  return Number.isFinite(days) && days > 0 ? Math.ceil(days / 7) : 0;
}

// Ô hỏi nhanh Trợ lý: bấm là mở ngăn Trợ lý và gửi câu hỏi.
function AskAssistant() {
  const { askInDock, assistant } = useAssistantContext();
  const busy = assistant.state.activeTurnId !== null;
  return (
    <Card title="Hỏi Trợ lý">
      <div className="flex flex-col gap-2">
        {ASK.map((q) => (
          <button
            key={q}
            type="button"
            disabled={busy}
            onClick={() => askInDock(q)}
            className="flex items-center justify-between gap-2 rounded-lg border-2 border-foreground/25 bg-background px-3 py-2 text-left text-sm transition-colors hover:border-primary/50 hover:bg-accent disabled:opacity-50"
          >
            <span>{q}</span>
            <Sparkles className="size-4 shrink-0 text-primary" aria-hidden="true" />
          </button>
        ))}
      </div>
    </Card>
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
                <Card>
                  <Stepper steps={journey(null)} />
                </Card>
                <Card title="Bắt đầu thực tập">
                  <EmptyState title="Bạn chưa có hồ sơ thực tập" action={<LinkButton href="/student/internship">Khai báo hồ sơ thực tập</LinkButton>}>
                    Khai báo hồ sơ (doanh nghiệp, thời gian, giấy tiếp nhận) để giảng viên xác nhận.
                  </EmptyState>
                </Card>
                <AskAssistant />
              </>
            );
          }
          const step = NEXT_STEP[row.status];
          const upcoming = d.milestones.filter((m) => m.status !== "accepted");
          const accepted = d.milestones.length - upcoming.length;
          const todo = upcoming.filter((m) => ["pending", "rejected", "overdue"].includes(m.status) && m.submittable).slice(0, 3);
          const expectedJournals = weeksBetween(row.start_date, row.end_date);
          const daysLeft = row.end_date ? Math.ceil((Date.parse(row.end_date) - nowMs) / DAY_MS) : null;
          const overdue = d.milestones.filter((m) => m.status === "overdue").length;
          return (
            <>
              <Card>
                <Stepper steps={journey(row.status)} />
              </Card>

              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard
                  label="Thời gian còn lại"
                  value={daysLeft === null ? "—" : daysLeft >= 0 ? `${daysLeft} ngày` : "Đã kết thúc"}
                  hint={`Đến ${fmtDate(row.end_date)}`}
                  icon={CalendarClock}
                />
                <StatCard label="Mốc hoàn tất" value={`${accepted}/${d.milestones.length}`} hint={overdue > 0 ? `${overdue} mốc quá hạn` : "Không có mốc quá hạn"} icon={CalendarCheck} tone={overdue > 0 ? "bad" : "good"} href="/student/milestones" />
                <StatCard label="Nhật ký đã nộp" value={expectedJournals > 0 ? `${d.journals.length}/${expectedJournals}` : d.journals.length} hint="Theo số tuần thực tập" icon={NotebookPen} href="/student/journal" />
                <StatCard label="Minh chứng" value={d.evidence.length} hint="Tệp đã nộp theo mốc" icon={Paperclip} href="/student/milestones" />
              </div>

              <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                <div className="space-y-5 lg:col-span-2">
                  <Card title="Việc cần làm">
                    <p className="mb-3 mt-0 flex flex-wrap items-center gap-2 text-sm">
                      <StatusBadge kind="internship" value={row.status} />
                      <span className="text-muted-foreground">
                        Khóa {row.cohort} · Giảng viên: {row.lecturer_name ?? "chưa phân công"} · {fmtDate(row.start_date)} → {fmtDate(row.end_date)} · {row.company_name || "chưa khai báo doanh nghiệp"}
                      </span>
                    </p>
                    {row.decision_reason && (
                      <p className="mb-3 mt-0 rounded-lg bg-orange-50 px-3 py-2 text-sm text-orange-900 ring-1 ring-inset ring-orange-600/20 dark:bg-orange-950 dark:text-orange-200">
                        Lý do từ giảng viên: {row.decision_reason}
                      </p>
                    )}
                    {step && (
                      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 border-foreground/25 bg-accent/60 px-4 py-3">
                        <span className="flex items-center gap-2 text-sm font-medium">
                          <ClipboardCheck className="size-4 text-primary" aria-hidden="true" />
                          {step.text}
                        </span>
                        <LinkButton href={step.href} variant={WAITING.has(row.status) ? "default" : "primary"}>
                          {step.action}
                        </LinkButton>
                      </div>
                    )}
                    {todo.length > 0 && (
                      <ul className="m-0 mt-3 list-none space-y-2 p-0">
                        {todo.map((m) => (
                          <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border-2 border-foreground/25 bg-background px-4 py-2.5 text-sm">
                            <span className="flex items-center gap-2">
                              <StatusBadge kind="milestone" value={m.status} /> <span>{m.next_action}</span>
                            </span>
                            <Link href="/student/milestones" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
                              Mở mốc {m.code} <ArrowRight className="size-3.5" aria-hidden="true" />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Card>

                  <Card title="Mốc thực tập">
                    {d.milestones.length === 0 ? (
                      <Empty>Chưa có mốc: mốc được tạo sau khi giảng viên xác nhận hồ sơ.</Empty>
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
                  </Card>
                </div>

                <div className="space-y-5">
                  <AskAssistant />
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
                    <Link href="/student/requests" className="text-sm font-medium text-primary hover:underline">
                      Xem tất cả yêu cầu
                    </Link>
                  </Card>
                </div>
              </div>
            </>
          );
        }}
      </Async>
    </Page>
  );
}
