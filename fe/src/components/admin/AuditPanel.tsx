"use client";

import { useState } from "react";
import { query } from "@/lib/http";
import { useApi } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/labels";
import type { AuditEvent } from "@/lib/types";
import { Async, Badge, Card, Empty, Field, Page, Table } from "@/components/ui/ui";

// Nhật ký kiểm toán chỉ-thêm: ai làm gì, khi nào (NF6: mọi quyết định truy vết được tới một người).
export default function AuditPanel() {
  const [entity, setEntity] = useState("");
  const state = useApi<AuditEvent[]>(`/api/admin/audit${query({ entity })}`);
  return (
    <Page title="Nhật ký kiểm toán">
      <Card>
        <Field label="Lọc theo thực thể">
          <select value={entity} onChange={(e) => setEntity(e.target.value)}>
            <option value="">Tất cả</option>
            {["internship", "outline", "milestone", "request", "credit_assessment", "risk_flag", "account", "session", "evidence", "journal", "agent_tool"].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </Field>
        <Async state={state}>
          {(list) =>
            list.length === 0 ? (
              <Empty>Không có bản ghi.</Empty>
            ) : (
              <Table head={["Thời điểm", "Người thực hiện", "Thực thể", "Hành động", "Lý do"]}>
                {list.map((a) => (
                  <tr key={a.id}>
                    <td>{fmtDateTime(a.at)}</td>
                    <td>
                      {a.actor_name ?? "—"} <Badge tone={a.actor_kind === "human" ? "neutral" : "warn"}>{a.actor_kind}</Badge> {a.actor_role}
                    </td>
                    <td>
                      {a.entity}
                      {a.entity_id ? ` #${a.entity_id}` : ""}
                    </td>
                    <td>{a.action}</td>
                    <td>{a.reason}</td>
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
