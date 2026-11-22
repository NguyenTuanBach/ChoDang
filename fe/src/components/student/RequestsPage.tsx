"use client";

import { useState } from "react";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import type { ExceptionType, RequestItem } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, FilePicker, Page, Row, StatusBadge } from "@/components/ui/ui";
import DownloadDoc from "./DownloadDoc";

export default function RequestsPage() {
  const requests = useApi<RequestItem[]>("/api/student/requests");
  const types = useApi<ExceptionType[]>("/api/exception-types");
  return (
    <Page title="Gia hạn và ngoại lệ">
      <Card title="Gửi yêu cầu ngoại lệ">
        <Async state={types}>{(list) => <ExceptionForm types={list} onDone={requests.reload} />}</Async>
      </Card>
      <Card title="Yêu cầu của tôi">
        <Async state={requests}>
          {(list) =>
            list.length === 0 ? (
              <Empty>Chưa có yêu cầu nào.</Empty>
            ) : (
              list.map((r) => <RequestRow key={r.id} item={r} reload={requests.reload} />)
            )
          }
        </Async>
      </Card>
    </Page>
  );
}

function ExceptionForm({ types, onDone }: { types: ExceptionType[]; onDone: () => void }) {
  const [code, setCode] = useState(types[0]?.code ?? "");
  const [reason, setReason] = useState("");
  const action = useAction(() => {
    setReason("");
    onDone();
  });
  const chosen = types.find((t) => t.code === code);
  return (
    <>
      <Field label="Loại ngoại lệ" hint={chosen?.affects_credit ? "Loại này ảnh hưởng tín chỉ: quản trị viên sẽ duyệt." : "Giảng viên sẽ duyệt."}>
        <select value={code} onChange={(e) => setCode(e.target.value)}>
          {types.map((t) => (
            <option key={t.code} value={t.code}>
              {t.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Lý do">
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <ErrorText message={action.error} />
      <Button variant="primary" disabled={action.busy || !code || !reason.trim()} onClick={() => void action.run(() => send("POST", "/api/student/requests/exception", { type_code: code, reason }))}>
        Gửi yêu cầu
      </Button>
    </>
  );
}

function RequestRow({ item, reload }: { item: RequestItem; reload: () => void }) {
  const cancel = useAction(reload);
  const attach = useAction(reload);
  return (
    <div style={{ marginBottom: "1rem" }}>
      <Row>
        <StatusBadge kind="request" value={item.status} />
        <strong>{item.kind === "milestone_extension" ? `Gia hạn mốc ${item.milestone_code} đến ${fmtDate(item.new_due_date)}` : item.exception_type_name}</strong>
        {item.affects_credit && <Badge tone="warn">Ảnh hưởng tín chỉ</Badge>}
        <span>{fmtDateTime(item.created_at)}</span>
      </Row>
      <p>Lý do: {item.reason}</p>
      {item.decision_reason && <p>Phản hồi: {item.decision_reason}</p>}
      {item.attachments.map((a) => (
        <div key={a.id}>
          <DownloadDoc href={`/api/request-attachments/${a.id}/download`} name={a.filename} />
        </div>
      ))}
      <ErrorText message={cancel.error ?? attach.error} />
      {item.status === "open" && (
        <Row>
          <FilePicker label="Đính kèm minh chứng" accept=".pdf,.png,.jpg,.jpeg,.docx" disabled={attach.busy} onFile={(file) => void attach.run(() => upload(`/api/student/requests/${item.id}/attachments`, file))} />
          <Button disabled={cancel.busy} onClick={() => void cancel.run(() => send("POST", `/api/student/requests/${item.id}/cancel`))}>
            Hủy yêu cầu
          </Button>
        </Row>
      )}
    </div>
  );
}
