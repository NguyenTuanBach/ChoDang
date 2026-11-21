"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import { QUEUE_KIND, fmtDate, fmtDateTime } from "@/lib/labels";
import type { QueueItem } from "@/lib/types";
import { Async, Badge, Card, Empty, Page, StatusBadge, Table } from "@/components/ui/ui";

// Hàng chờ duyệt xếp theo ưu tiên (hạn gần, rủi ro cao, chờ lâu) — A12.
export default function QueuePanel({ base }: { base: "/lecturer" | "/admin" }) {
  const state = useApi<QueueItem[]>("/api/queue");
  return (
    <Page title="Hàng chờ duyệt">
      <Card>
        <Async state={state}>
          {(items) =>
            items.length === 0 ? (
              <Empty>Không có việc nào đang chờ bạn.</Empty>
            ) : (
              <Table head={["Ưu tiên", "Loại", "Sinh viên", "Nội dung", "Chờ từ", "Hạn", ""]}>
                {items.map((i) => (
                  <tr key={`${i.kind}-${i.ref_id}`}>
                    <td>
                      <Badge tone={i.priority >= 60 ? "bad" : i.priority >= 35 ? "warn" : "neutral"}>{i.priority}</Badge>
                    </td>
                    <td>{QUEUE_KIND[i.kind] ?? i.kind}</td>
                    <td>{i.student_name}</td>
                    <td>
                      {i.severity && <StatusBadge kind="severity" value={i.severity} />} {i.title}
                    </td>
                    <td>{fmtDateTime(i.since)}</td>
                    <td>{fmtDate(i.due_date)}</td>
                    <td>
                      <Link href={i.kind === "request" ? `${base}/requests` : i.kind === "risk_flag" && base === "/lecturer" ? "/lecturer/flags" : `${base}/internships/${i.internship_id}`}>Mở</Link>
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
