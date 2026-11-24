"use client";

import { ArrowLeft, Paperclip } from "lucide-react";
import { useRef, useState } from "react";
import NoticeCard from "@/components/ui/notice-card";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, FilePicker, Page, Row, StatusBadge, Table } from "@/components/ui/ui";
import { useAction, useApi } from "@/lib/hooks";
import { send, upload } from "@/lib/http";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import type { ExceptionType, InternshipDetail, RequestItem } from "@/lib/types";
import DownloadDoc from "./DownloadDoc";

const MAX_MB = 10;
// Mọi nút "Áp dụng" cùng một kiểu và độ rộng để thẳng hàng.
const APPLY = "w-24";
// Khớp BE (`_ACTIVE` ở request_service): chỉ gửi đơn khi hồ sơ đã được giảng viên xác nhận và đang trong quá trình thực tập.
const REQUESTABLE = new Set(["confirmed", "in_progress", "pending_credit"]);
const approverOf = (t: ExceptionType) => (t.affects_credit ? "Quản trị viên (ảnh hưởng tín chỉ)" : "Giảng viên");

// Gửi đơn: danh sách các loại đơn (bấm "Áp dụng" để mở form), kèm danh sách đơn đã gửi của tôi.
export default function RequestsPage() {
  const requests = useApi<RequestItem[]>("/api/student/requests");
  const types = useApi<ExceptionType[]>("/api/exception-types");
  const profile = useApi<InternshipDetail>("/api/student/internship");
  const [chosen, setChosen] = useState<ExceptionType | null>(null);
  const [extension, setExtension] = useState(false);
  const status = profile.data?.internship?.status;
  const canApply = status !== undefined && REQUESTABLE.has(status);

  if (extension) {
    return (
      <Page title="Gửi đơn">
        <ExtensionRequestForm
          detail={profile.data ?? null}
          onBack={() => setExtension(false)}
          onDone={() => {
            setExtension(false);
            requests.reload();
          }}
        />
      </Page>
    );
  }

  if (chosen) {
    return (
      <Page title="Gửi đơn">
        <RequestForm
          type={chosen}
          studentCode={profile.data?.internship?.student_code ?? null}
          onBack={() => setChosen(null)}
          onDone={() => {
            setChosen(null);
            requests.reload();
          }}
        />
      </Page>
    );
  }

  return (
    <Page title="Gửi đơn">
      {!profile.loading && !canApply && (
        <NoticeCard tone="warning" title="Chưa gửi được đơn">
          {status === undefined ? "Bạn chưa đăng ký hồ sơ thực tập." : "Hồ sơ chưa được giảng viên xác nhận hoặc đã kết thúc."} Đơn chỉ gửi được khi hồ sơ đang trong quá trình thực tập.
        </NoticeCard>
      )}
      <Card title="Loại đơn" className="bg-background">
        <Async state={types}>
          {(list) => (
            <Table head={["STT", "Loại đơn", "Người duyệt", "Thao tác"]}>
              <tr>
                <td>1</td>
                <td>Gia hạn mốc thực tập</td>
                <td>Giảng viên</td>
                <td>
                  <Button variant="primary" className={APPLY} disabled={!canApply} onClick={() => setExtension(true)}>
                    Áp dụng
                  </Button>
                </td>
              </tr>
              {list
                .filter((t) => t.active !== false)
                .map((t, i) => (
                  <tr key={t.code}>
                    <td>{i + 2}</td>
                    <td>{t.name}</td>
                    <td>{approverOf(t)}</td>
                    <td>
                      <Button variant="primary" className={APPLY} disabled={!canApply} onClick={() => setChosen(t)}>
                        Áp dụng
                      </Button>
                    </td>
                  </tr>
                ))}
            </Table>
          )}
        </Async>
      </Card>

      <Card title="Đơn của tôi" className="bg-background">
        <Async state={requests}>
          {(list) =>
            list.length === 0 ? (
              <Empty>Chưa có đơn nào.</Empty>
            ) : (
              <div className="space-y-3">
                {list.map((r) => (
                  <RequestRow key={r.id} item={r} reload={requests.reload} />
                ))}
              </div>
            )
          }
        </Async>
      </Card>
    </Page>
  );
}

// Form gửi đơn cho một loại đơn: loại đơn và MSSV chỉ đọc, nhập lý do, đính kèm tệp (không bắt buộc).
function RequestForm({ type, studentCode, onBack, onDone }: { type: ExceptionType; studentCode: string | null; onBack: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  // Đơn đã tạo nhưng tải tệp lỗi: thử lại chỉ tải tệp, không tạo đơn trùng.
  const [createdId, setCreatedId] = useState<number | null>(null);
  const submit = useAction(onDone);
  const tooBig = file !== null && file.size > MAX_MB * 1024 * 1024;

  return (
    <Card title="Gửi đơn" className="bg-background">
      <Field label="Loại đơn" required>
        <div className="rounded-lg border-2 border-foreground/25 bg-muted px-3 py-2 text-sm">{type.name}</div>
      </Field>
      <p className="mb-3 mt-0 text-sm text-muted-foreground">
        Người duyệt: <strong className="text-foreground">{approverOf(type)}</strong>
      </p>
      <Field label="MSSV" required>
        <input value={studentCode ?? ""} placeholder="Chưa có MSSV - nhờ giảng viên hoặc quản trị viên cập nhật" disabled readOnly />
      </Field>
      <Field label="Lý do" required>
        <textarea placeholder="Nhập lý do" value={reason} disabled={createdId !== null} onChange={(e) => setReason(e.target.value)} style={{ minHeight: "6rem" }} />
      </Field>
      <div className="mb-3 flex flex-col gap-1.5 text-sm">
        <span className="font-medium">Tệp đính kèm</span>
        <input ref={fileInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" onClick={() => fileInput.current?.click()}>
            <Paperclip className="size-4" aria-hidden="true" />
            {file ? "Chọn tệp khác" : "Chọn tệp"}
          </Button>
          {file ? (
            <span className="flex items-center gap-2">
              <span className="break-all">{file.name}</span>
              <button
                type="button"
                className="text-muted-foreground underline underline-offset-2 hover:text-foreground"
                onClick={() => {
                  setFile(null);
                  if (fileInput.current) fileInput.current.value = "";
                }}
              >
                Bỏ chọn
              </button>
            </span>
          ) : (
            <span className="text-muted-foreground">Chưa chọn tệp</span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">Tối đa {MAX_MB}MB (.pdf, .docx, .png, .jpg)</span>
      </div>
      {tooBig && <ErrorText message={`Tệp vượt quá ${MAX_MB}MB`} />}
      <ErrorText message={submit.error} />
      <Row>
        <Button
          variant="primary"
          disabled={submit.busy || tooBig || !reason.trim()}
          onClick={() =>
            void submit.run(async () => {
              let id = createdId;
              if (id === null) {
                id = (await send<{ id: number }>("POST", "/api/student/requests/exception", { type_code: type.code, reason })).id;
                setCreatedId(id);
              }
              if (file) await upload(`/api/student/requests/${id}/attachments`, file);
            })
          }
        >
          Gửi đơn
        </Button>
        <Button onClick={onBack}>
          <ArrowLeft aria-hidden className="size-4" />
          Quay lại
        </Button>
      </Row>
    </Card>
  );
}

function RequestRow({ item, reload }: { item: RequestItem; reload: () => void }) {
  const cancel = useAction(reload);
  const attach = useAction(reload);
  return (
    <div className="rounded-lg border-2 border-foreground/25 bg-background p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge kind="request" value={item.status} />
        <strong>{item.kind === "milestone_extension" ? `Gia hạn mốc ${item.milestone_code} đến ${fmtDate(item.new_due_date)}` : item.exception_type_name}</strong>
        {item.affects_credit && <Badge tone="warn">Ảnh hưởng tín chỉ</Badge>}
        <span className="ml-auto text-xs text-muted-foreground">{fmtDateTime(item.created_at)}</span>
      </div>
      <p className="m-0 mt-2">Lý do: {item.reason}</p>
      {item.decision_reason && <p className="m-0 mt-1 text-muted-foreground">Phản hồi: {item.decision_reason}</p>}
      {item.attachments.map((a) => (
        <div key={a.id} className="mt-1">
          <DownloadDoc href={`/api/request-attachments/${a.id}/download`} name={a.filename} />
        </div>
      ))}
      <ErrorText message={cancel.error ?? attach.error} />
      {item.status === "open" && (
        <div className="mt-3">
          <Row>
            <FilePicker label="Đính kèm minh chứng" accept=".pdf,.png,.jpg,.jpeg,.docx" disabled={attach.busy} onFile={(file) => void attach.run(() => upload(`/api/student/requests/${item.id}/attachments`, file))} />
            <Button disabled={cancel.busy} onClick={() => void cancel.run(() => send("POST", `/api/student/requests/${item.id}/cancel`))}>
              Hủy đơn
            </Button>
          </Row>
        </div>
      )}
    </div>
  );
}

// Đơn gia hạn mốc: chọn mốc chưa nộp/chưa được chấp nhận, hạn mới đề nghị và lý do (gửi giảng viên duyệt).
function ExtensionRequestForm({ detail, onBack, onDone }: { detail: InternshipDetail | null; onBack: () => void; onDone: () => void }) {
  const working = ["in_progress", "pending_credit"].includes(detail?.internship?.status ?? "");
  const options = (detail?.milestones ?? []).filter((m) => m.stored_status !== "accepted" && m.stored_status !== "submitted");
  const [code, setCode] = useState("");
  const [due, setDue] = useState("");
  const [reason, setReason] = useState("");
  const action = useAction(onDone);
  const chosen = options.find((m) => m.code === code);

  return (
    <Card title="Gửi đơn — Gia hạn mốc thực tập" className="bg-background">
      {!working ? (
        <Empty>Chỉ gửi được đơn gia hạn khi bạn đang thực tập.</Empty>
      ) : options.length === 0 ? (
        <Empty>Không có mốc nào có thể gia hạn.</Empty>
      ) : (
        <>
          <p className="mb-3 mt-0 text-sm text-muted-foreground">
            Người duyệt: <strong className="text-foreground">Giảng viên</strong>
          </p>
          <Field label="Mốc cần gia hạn" required>
            <select
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setDue("");
              }}
            >
              <option value="" disabled>
                Chọn mốc
              </option>
              {options.map((m) => (
                <option key={m.code} value={m.code}>
                  {m.code} — {m.name} (hạn {fmtDate(m.due_date)})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Hạn mới đề nghị" required>
            <input type="date" value={due} min={chosen?.due_date} disabled={!chosen} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label="Lý do" required>
            <textarea placeholder="Nhập lý do" value={reason} onChange={(e) => setReason(e.target.value)} style={{ minHeight: "6rem" }} />
          </Field>
          <ErrorText message={action.error} />
        </>
      )}
      <Row>
        {working && options.length > 0 && (
          <Button variant="primary" disabled={action.busy || !code || !due || !reason.trim()} onClick={() => void action.run(() => send("POST", "/api/student/requests/extension", { milestone_code: code, new_due_date: due, reason }))}>
            Gửi đơn
          </Button>
        )}
        <Button onClick={onBack}>Quay lại</Button>
      </Row>
    </Card>
  );
}
