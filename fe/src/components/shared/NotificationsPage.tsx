"use client";

import Link from "next/link";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/labels";
import type { NotificationItem } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, Page } from "@/components/ui/ui";

export default function NotificationsPage() {
  const state = useApi<{ unread: number; items: NotificationItem[] }>("/api/notifications");
  const readAll = useAction(state.reload);
  return (
    <Page title="Thông báo" actions={<Button disabled={readAll.busy} onClick={() => void readAll.run(() => send("POST", "/api/notifications/read"))}>Đánh dấu đã đọc tất cả</Button>}>
      <Card>
        <Async state={state}>
          {(d) =>
            d.items.length === 0 ? (
              <Empty>Chưa có thông báo.</Empty>
            ) : (
              d.items.map((n) => (
                <div key={n.id} style={{ marginBottom: "0.75rem" }}>
                  {!n.read_at && <Badge tone="warn">Mới</Badge>} <strong>{n.title}</strong> <small>{fmtDateTime(n.created_at)}</small>
                  {n.body && <div style={{ whiteSpace: "pre-wrap" }}>{n.body}</div>}
                  {n.link.startsWith("/") && <Link href={n.link}>Mở</Link>}
                </div>
              ))
            )
          }
        </Async>
      </Card>
    </Page>
  );
}
