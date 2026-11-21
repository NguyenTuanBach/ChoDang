"use client";

import { AlarmClock, Flag, Hourglass, Inbox, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import { Async, Badge, Card, EmptyState, Page, StatCard, StatusBadge } from "@/components/ui/ui";
import { useApi } from "@/lib/hooks";
import { INTERNSHIP_STATUS, QUEUE_KIND, fmtDate, fmtDateTime } from "@/lib/labels";
import type { Dashboard, QueueItem } from "@/lib/types";
import { useCurrentUser } from "@/lib/user-context";
import { cn } from "@/lib/utils";

function linkOf(i: QueueItem, base: "/lecturer" | "/admin") {
  if (i.kind === "request") return `${base}/requests`;
  if (i.kind === "risk_flag" && base === "/lecturer") return "/lecturer/flags";
  return `${base}/internships/${i.internship_id}`;
}

const SEGMENT = ["bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4", "bg-chart-5", "bg-muted-foreground"];

// Thanh xếp chồng phân bố hồ sơ theo trạng thái + chú giải (màu lấy từ bảng chart của chủ đề).
function StatusDistribution({ rows }: { rows: { status: string; n: number }[] }) {
  const total = rows.reduce((s, r) => s + r.n, 0);
  if (total === 0) return <EmptyState>Chưa có hồ sơ nào trong phạm vi của bạn.</EmptyState>;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-muted" role="img" aria-label="Phân bố hồ sơ theo trạng thái">
        {rows.map((r, i) => (
          <span key={r.status} className={SEGMENT[i % SEGMENT.length]} style={{ width: `${(r.n / total) * 100}%` }} title={`${INTERNSHIP_STATUS[r.status] ?? r.status}: ${r.n}`} />
        ))}
      </div>
      <ul className="m-0 mt-3 grid list-none grid-cols-1 gap-x-4 gap-y-1.5 p-0 text-sm sm:grid-cols-2">
        {rows.map((r, i) => (
          <li key={r.status} className="flex items-center gap-2">
            <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-full", SEGMENT[i % SEGMENT.length])} />
            <span className="min-w-0 flex-1 truncate">{INTERNSHIP_STATUS[r.status] ?? r.status}</span>
            <strong className="tabular-nums">{r.n}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Trang chủ của giảng viên/quản trị viên: số liệu nhanh + hàng chờ duyệt xếp theo ưu tiên (hạn gần, rủi ro cao, chờ lâu) — A12.
// Dải màu bên trái mỗi việc: đỏ = gấp, cam = nên xử lý sớm.
export default function QueuePanel({ base }: { base: "/lecturer" | "/admin" }) {
  const user = useCurrentUser();
  const queue = useApi<QueueItem[]>("/api/queue");
  const dash = useApi<Dashboard>("/api/dashboard");
  const isAdmin = base === "/admin";
  const firstName = user.full_name.replace(/\(.*?\)/g, "").trim() || user.email;

  const d = dash.data;
  const openFlags = d ? d.flags.filter((f) => f.status === "open" || f.status === "acknowledged").reduce((s, f) => s + f.n, 0) : null;
  const awaitingCredit = d ? (d.credit_outcomes.find((c) => c.status === "lecturer_passed")?.n ?? 0) : null;
  const syncIssues = d ? d.sync_jobs.filter((s) => s.status !== "synced").reduce((s, r) => s + r.n, 0) : null;

  return (
    <Page title={`Xin chào, ${firstName}`} description={isAdmin ? "Việc cần xử lý và tình hình thực tập toàn khóa." : "Việc cần duyệt và tình hình sinh viên bạn phụ trách."}>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Đang thực tập" value={d?.active_internships ?? "…"} hint={isAdmin ? "Toàn khóa" : "Sinh viên bạn phụ trách"} icon={Users} href={`${base}/internships`} />
        <StatCard
          label="Hồ sơ trễ hạn"
          value={d?.late_internships ?? "…"}
          hint="Có mốc quá hạn"
          icon={AlarmClock}
          tone={d && d.late_internships > 0 ? "bad" : "good"}
          href={`${base}/internships`}
        />
        <StatCard label="Cờ rủi ro mở" value={openFlags ?? "…"} hint="Đang mở hoặc đã ghi nhận" icon={Flag} tone={openFlags ? "warn" : "good"} href={isAdmin ? "/dashboard" : "/lecturer/flags"} />
        {isAdmin ? (
          <StatCard label="Chờ phê duyệt tín chỉ" value={awaitingCredit ?? "…"} hint={syncIssues ? `${syncIssues} việc đồng bộ LMS chưa xong` : "Việc đồng bộ LMS ổn"} icon={ShieldCheck} tone={awaitingCredit ? "warn" : "good"} href="/admin/credit" />
        ) : (
          <StatCard label="Việc chờ bạn" value={queue.data?.length ?? "…"} hint="Trong hàng chờ bên dưới" icon={Hourglass} tone={queue.data?.length ? "warn" : "good"} />
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card title="Hàng chờ duyệt" description="Xếp theo mức ưu tiên">
            <Async state={queue}>
              {(items) =>
                items.length === 0 ? (
                  <EmptyState icon={Inbox} title="Không có việc nào đang chờ bạn">
                    Hồ sơ, đề cương, mốc và yêu cầu mới sẽ hiện ở đây.
                  </EmptyState>
                ) : (
                  <ul className="m-0 list-none space-y-2 p-0">
                    {items.map((i) => {
                      const urgent = i.priority >= 60;
                      const soon = i.priority >= 35;
                      return (
                        <li key={`${i.kind}-${i.ref_id}`}>
                          <Link
                            href={linkOf(i, base)}
                            className={cn(
                              "flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-l-4 border-border bg-background px-4 py-3 text-foreground no-underline transition-colors hover:bg-muted",
                              urgent ? "border-l-destructive" : soon ? "border-l-orange-500" : "border-l-border",
                            )}
                          >
                            <span className="min-w-0 flex-1">
                              <span className="block text-xs font-medium text-muted-foreground">{QUEUE_KIND[i.kind] ?? i.kind}</span>
                              <span className="block text-sm font-semibold">{i.student_name}</span>
                              <span className="block text-sm">
                                {i.severity && <StatusBadge kind="severity" value={i.severity} />} {i.title}
                              </span>
                            </span>
                            <span className="flex flex-col items-end gap-1 text-xs text-muted-foreground">
                              <Badge tone={urgent ? "bad" : soon ? "action" : "neutral"}>Ưu tiên {i.priority}</Badge>
                              <span>Chờ từ {fmtDateTime(i.since)}</span>
                              {i.due_date && <span>Hạn {fmtDate(i.due_date)}</span>}
                            </span>
                            <span className="text-sm font-medium text-primary">Mở →</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                )
              }
            </Async>
          </Card>
        </div>

        <Card title="Hồ sơ theo trạng thái">
          <Async state={dash}>{(data) => <StatusDistribution rows={data.internships_by_status} />}</Async>
        </Card>
      </div>
    </Page>
  );
}
