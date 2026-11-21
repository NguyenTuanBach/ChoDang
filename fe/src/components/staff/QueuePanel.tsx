"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import { QUEUE_KIND, fmtDate, fmtDateTime } from "@/lib/labels";
import type { QueueItem } from "@/lib/types";
import { Async, Badge, Empty, Page, StatusBadge } from "@/components/ui/ui";

function linkOf(i: QueueItem, base: "/lecturer" | "/admin") {
  if (i.kind === "request") return `${base}/requests`;
  if (i.kind === "risk_flag" && base === "/lecturer") return "/lecturer/flags";
  return `${base}/internships/${i.internship_id}`;
}

// Hàng chờ duyệt xếp theo ưu tiên (hạn gần, rủi ro cao, chờ lâu) — A12. Dải màu bên trái: đỏ = gấp, cam = nên xử lý sớm.
export default function QueuePanel({ base }: { base: "/lecturer" | "/admin" }) {
  const state = useApi<QueueItem[]>("/api/queue");
  return (
    <Page title="Hàng chờ duyệt">
      <Async state={state}>
        {(items) =>
          items.length === 0 ? (
            <Empty>Không có việc nào đang chờ bạn. 🎉</Empty>
          ) : (
            <ul className="m-0 list-none space-y-2 p-0">
              {items.map((i) => {
                const urgent = i.priority >= 60;
                const soon = i.priority >= 35;
                return (
                  <li key={`${i.kind}-${i.ref_id}`}>
                    <Link
                      href={linkOf(i, base)}
                      className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-l-4 border-border bg-surface px-4 py-3 text-fg no-underline shadow-sm transition-colors hover:bg-soft ${urgent ? "border-l-red-600" : soon ? "border-l-orange-500" : "border-l-border"}`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-medium text-muted">{QUEUE_KIND[i.kind] ?? i.kind}</span>
                        <span className="block text-sm font-semibold">{i.student_name}</span>
                        <span className="block text-sm">
                          {i.severity && <StatusBadge kind="severity" value={i.severity} />} {i.title}
                        </span>
                      </span>
                      <span className="flex flex-col items-end gap-1 text-xs text-muted">
                        <Badge tone={urgent ? "bad" : soon ? "action" : "neutral"}>Ưu tiên {i.priority}</Badge>
                        <span>Chờ từ {fmtDateTime(i.since)}</span>
                        {i.due_date && <span>Hạn {fmtDate(i.due_date)}</span>}
                      </span>
                      <span className="text-sm font-medium text-blue-600">Mở →</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )
        }
      </Async>
    </Page>
  );
}
