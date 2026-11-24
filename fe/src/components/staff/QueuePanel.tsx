"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Async, Badge, Button, Card, EmptyState, Page, StatCard, isDoneStatus, outcomeBg } from "@/components/ui/ui";
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

// Hoàn thành = xanh lá, chưa hoàn thành = đỏ.
const segmentClass = (status: string) => outcomeBg(status);

// Bộ lọc hàng chờ (làm ở trình duyệt): theo mức gấp, rủi ro, quá hạn hoặc loại việc.
const startOfToday = () => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
};
const FILTERS: { key: string; label: string; match: (i: QueueItem) => boolean }[] = [
  { key: "all", label: "Tất cả", match: () => true },
  { key: "urgent", label: "Gấp", match: (i) => i.priority >= 60 },
  { key: "risk", label: "Rủi ro", match: (i) => i.kind === "risk_flag" },
  { key: "overdue", label: "Quá hạn", match: (i) => !!i.due_date && new Date(i.due_date).getTime() < startOfToday() },
  { key: "internship", label: "Hồ sơ", match: (i) => i.kind === "internship_submitted" },
  { key: "outline", label: "Đề cương", match: (i) => i.kind === "outline_submitted" },
  { key: "milestone", label: "Mốc", match: (i) => i.kind === "milestone_submitted" },
  { key: "request", label: "Yêu cầu", match: (i) => i.kind === "request" },
  { key: "credit", label: "Tín chỉ", match: (i) => i.kind === "credit_assessment" || i.kind === "credit_approval" },
];

// Thanh xếp chồng phân bố hồ sơ theo trạng thái + chú giải (màu lấy từ bảng chart của chủ đề).
function StatusDistribution({ rows: unsorted }: { rows: { status: string; n: number }[] }) {
  // Cùng màu nằm liền nhau: xanh lá (hoàn thành/đang tốt) trước, đỏ (chưa hoàn thành) sau; trong mỗi nhóm giữ nguyên thứ tự.
  const rows = [...unsorted].sort((a, b) => Number(isDoneStatus(b.status)) - Number(isDoneStatus(a.status)));
  const total = rows.reduce((s, r) => s + r.n, 0);
  if (total === 0) return <EmptyState noIcon>Chưa có hồ sơ nào trong phạm vi của bạn.</EmptyState>;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full border border-foreground/25 bg-muted" role="img" aria-label="Phân bố hồ sơ theo trạng thái">
        {rows.map((r) => (
          <span key={r.status} className={segmentClass(r.status)} style={{ width: `${(r.n / total) * 100}%` }} title={`${INTERNSHIP_STATUS[r.status] ?? r.status}: ${r.n}`} />
        ))}
      </div>
      <ul className="m-0 mt-3 grid list-none grid-cols-1 gap-y-2 p-0 text-sm">
        {rows.map((r) => (
          <li key={r.status} className="flex items-center gap-2">
            <span aria-hidden="true" className={cn("size-2.5 shrink-0 rounded-full", segmentClass(r.status))} />
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
// Bộ lọc ban đầu lấy từ `?kind=` (trợ lý mở hàng chờ kèm bộ lọc, khóa khai báo ở lib/nav.ts); giá trị lạ thì "Tất cả".
// Query đổi (trợ lý lọc lại khi đang ở trang) thì dựng lại phần thân để nhận bộ lọc mới.
export default function QueuePanel({ base }: { base: "/lecturer" | "/admin" }) {
  return (
    <Suspense fallback={null}>
      <QueueFromUrl base={base} />
    </Suspense>
  );
}

function QueueFromUrl({ base }: { base: "/lecturer" | "/admin" }) {
  const kind = useSearchParams().get("kind") ?? "";
  const initial = FILTERS.some((f) => f.key === kind) ? kind : "all";
  return <QueueView key={initial} base={base} initialFilter={initial} />;
}

function QueueView({ base, initialFilter }: { base: "/lecturer" | "/admin"; initialFilter: string }) {
  const user = useCurrentUser();
  const queue = useApi<QueueItem[]>("/api/queue");
  const dash = useApi<Dashboard>("/api/dashboard");
  const isAdmin = base === "/admin";
  const [filter, setFilter] = useState(initialFilter);
  const firstName = user.full_name.replace(/\(.*?\)/g, "").trim() || user.email;

  const d = dash.data;
  const openFlags = d ? d.flags.filter((f) => f.status === "open" || f.status === "acknowledged").reduce((s, f) => s + f.n, 0) : null;
  const awaitingCredit = d ? (d.credit_outcomes.find((c) => c.status === "lecturer_passed")?.n ?? 0) : null;
  const syncIssues = d ? d.sync_jobs.filter((s) => s.status !== "synced").reduce((s, r) => s + r.n, 0) : null;

  return (
    <Page title={`Xin chào, ${firstName}`} description={isAdmin ? "Việc cần xử lý và tình hình thực tập toàn khóa." : "Việc cần duyệt và tình hình sinh viên bạn phụ trách."}>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Đang thực tập" value={d?.active_internships ?? "…"} hint={isAdmin ? "Toàn khóa" : "Sinh viên bạn phụ trách"} href={`${base}/internships`} />
        <StatCard
          label="Hồ sơ trễ hạn"
          value={d?.late_internships ?? "…"}
          hint="Có mốc quá hạn"
         
          tone={d && d.late_internships > 0 ? "bad" : "good"}
          href={`${base}/internships`}
        />
        <StatCard label="Cờ rủi ro mở" value={openFlags ?? "…"} hint="Đang mở hoặc đã ghi nhận" tone={openFlags ? "warn" : "good"} href={isAdmin ? "/dashboard" : "/lecturer/flags"} />
        {isAdmin ? (
          <StatCard label="Chờ phê duyệt tín chỉ" value={awaitingCredit ?? "…"} hint={syncIssues ? `${syncIssues} việc đồng bộ LMS chưa xong` : "Việc đồng bộ LMS ổn"} tone={awaitingCredit ? "warn" : "good"} href="/admin/credit" />
        ) : (
          <StatCard label="Việc chờ bạn" value={queue.data?.length ?? "…"} hint="Trong hàng chờ bên dưới" tone={queue.data?.length ? "warn" : "good"} />
        )}
      </div>

      <Card title="Hồ sơ theo trạng thái">
        <Async state={dash}>{(data) => <StatusDistribution rows={data.internships_by_status} />}</Async>
      </Card>

      <div>
        <div>
          <Card title="Hàng chờ duyệt">
            <Async state={queue}>
              {(items) =>
                items.length === 0 ? (
                  <EmptyState noIcon title="Không có việc nào đang chờ bạn">
                    Hồ sơ, đề cương, mốc và yêu cầu mới sẽ hiện ở đây.
                  </EmptyState>
                ) : (
                  <>
                  <div className="mb-4 flex flex-wrap gap-2">
                    {FILTERS.map((f) => {
                      const n = items.filter(f.match).length;
                      if (f.key !== "all" && n === 0 && filter !== f.key) return null;
                      return (
                        <Button key={f.key} variant={filter === f.key ? "primary" : "default"} onClick={() => setFilter(f.key)}>
                          {f.label} ({n})
                        </Button>
                      );
                    })}
                  </div>
                  {items.filter((FILTERS.find((f) => f.key === filter) ?? FILTERS[0]).match).length === 0 && <EmptyState noIcon title="Không có việc nào thuộc bộ lọc này" />}
                  <ul className="m-0 list-none space-y-3 p-0">
                    {items.filter((FILTERS.find((f) => f.key === filter) ?? FILTERS[0]).match).map((i) => {
                      const urgent = i.priority >= 60;
                      const soon = i.priority >= 35;
                      return (
                        <li key={`${i.kind}-${i.ref_id}`}>
                          <Link
                            href={linkOf(i, base)}
                            className={cn(
                              "flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border-2 border-foreground/25 bg-background px-5 py-4 text-foreground no-underline transition-colors hover:bg-muted",
                              urgent ? "border-l-[6px] border-l-destructive" : soon ? "border-l-[6px] border-l-orange-500" : "",
                            )}
                          >
                            <span className="min-w-0 flex-1">
                              <span className="block text-xs font-medium text-muted-foreground">{QUEUE_KIND[i.kind] ?? i.kind}</span>
                              <span className="block text-sm font-semibold">{i.student_name}</span>
                              <span className="block text-sm">
                                {i.title}
                              </span>
                            </span>
                            <span className="flex flex-col items-end gap-1 text-xs text-muted-foreground">
                              {urgent ? <Badge tone="bad">Gấp</Badge> : soon ? <Badge tone="action">Nên xử lý sớm</Badge> : null}
                              <span>Chờ từ {fmtDateTime(i.since)}</span>
                              {i.due_date && <span>Hạn {fmtDate(i.due_date)}</span>}
                            </span>
                            <span className="ml-2 inline-flex h-9 items-center rounded-lg border-2 border-foreground/25 bg-card px-4 text-sm font-medium">Mở</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                  </>
                )
              }
            </Async>
          </Card>
        </div>
      </div>
    </Page>
  );
}
