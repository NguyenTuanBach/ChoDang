"use client";

import { Check, FileText, Minus } from "lucide-react";
import { useState } from "react";
import FormDialog from "@/components/ui/dialog";
import { usePendingAutofill, type PendingAutofill } from "@/lib/autofill";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import type { InternshipDetail, Milestone } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, FilePicker, Page, Row, StatusBadge } from "@/components/ui/ui";
import { cn } from "@/lib/utils";
import NoticeCard from "@/components/ui/notice-card";
import EvidenceFieldsForm from "./EvidenceFieldsForm";
import EvidencePreviewDialog from "./EvidencePreviewDialog";

//: Mốc có giấy xác nhận / phiếu đánh giá của doanh nghiệp: AI đọc giấy để điền thông tin.
const COMPLETION_CODE = "M5";

// Các mốc bắt buộc dạng dòng thời gian dọc: mốc xong có dấu tích xanh, mốc tiếp theo nổi bật, mốc quá hạn viền đỏ.
export default function MilestonesPage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  // Giấy xác nhận đính kèm trong ngăn Trợ lý: BE đã lưu làm minh chứng M5; tải lại để thấy tệp, rồi điền nháp vào form của tệp đó.
  const auto = usePendingAutofill("completion_letter", state.reload);
  return (
    <Page title="Mốc và minh chứng">
      <Async state={state}>
        {(d) => {
          if (!d.internship) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;
          if (d.milestones.length === 0) return <Empty>Mốc sẽ xuất hiện sau khi giảng viên xác nhận hồ sơ.</Empty>;
          const currentId = d.milestones.find((m) => m.stored_status !== "accepted")?.id;
          return (
            <Card title="Các mốc bắt buộc">
              <ol className="m-0 list-none p-0">
                {d.milestones.map((m, i) => (
                  <MilestoneStep
                    key={m.id}
                    index={i + 1}
                    last={i === d.milestones.length - 1}
                    current={m.id === currentId}
                    milestone={m}
                    detail={d}
                    reload={state.reload}
                    autofill={m.code === COMPLETION_CODE ? auto.value : null}
                    autofillNonce={auto.nonce}
                    onAutofillSaved={auto.clear}
                  />
                ))}
              </ol>
            </Card>
          );
        }}
      </Async>
    </Page>
  );
}

function MilestoneStep({
  index,
  last,
  current,
  milestone: m,
  detail,
  reload,
  autofill,
  autofillNonce,
  onAutofillSaved,
}: {
  index: number;
  last: boolean;
  current: boolean;
  milestone: Milestone;
  detail: InternshipDetail;
  reload: () => void;
  autofill: PendingAutofill | null;
  autofillNonce: number;
  onAutofillSaved: () => void;
}) {
  // Các lần nộp minh chứng của mốc, theo thứ tự thời gian: Lần 1, Lần 2...
  const evidence = detail.evidence.filter((e) => e.milestone_code === m.code).sort((a, b) => a.submitted_at.localeCompare(b.submitted_at) || a.id - b.id);
  const working = ["in_progress", "pending_credit"].includes(detail.internship?.status ?? "");
  const locked = m.stored_status === "submitted" || m.stored_status === "accepted";
  const done = m.stored_status === "accepted";
  const overdue = !done && m.days_left < 0;
  const up = useAction(reload);
  const submit = useAction(reload);
  // Minh chứng đang chờ SV xác nhận thu hồi (popup xác nhận).
  const [withdrawTarget, setWithdrawTarget] = useState<{ id: number; n: number } | null>(null);
  const withdraw = useAction(() => {
    setWithdrawTarget(null);
    reload();
  });
  const [extending, setExtending] = useState(false);
  const [autoExtractId, setAutoExtractId] = useState<number | null>(null);
  // Tệp vừa chọn, chờ xem lại trong popup rồi mới tải lên.
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  // Còn thu hồi được (mốc chưa nộp/chấp nhận): các dòng minh chứng chừa chỗ cho nút dấu trừ để thẳng hàng.
  const canWithdraw = working && !locked;

  // Minh chứng dạng PDF/ảnh (mọi mốc): tải lên xong thì AI đọc luôn và điền sẵn form "Thông tin trên giấy" (SV kiểm rồi xác nhận).
  async function uploadEvidence(file: File) {
    let id: number | null = null;
    const ok = await up.run(async () => {
      id = (await upload<{ id: number }>(`/api/student/milestones/${m.code}/evidence`, file)).id;
    });
    if (ok && id !== null && /\.(pdf|png|jpe?g)$/i.test(file.name)) setAutoExtractId(id);
  }

  return (
    <li className={cn("relative grid grid-cols-[2.5rem_1fr] gap-x-4", !last && "pb-8")}>
      {!last && <span aria-hidden="true" className={cn("absolute bottom-0 left-5 top-10 w-0 -translate-x-1/2 border-l-2", done ? "border-solid border-green-600" : "border-dashed border-beige-strong")} />}
      <span
        className={cn(
          "relative z-10 flex size-10 items-center justify-center rounded-full border-2 text-sm font-semibold",
          done && "border-green-600 bg-green-600 text-white",
          !done && current && "border-beige-strong bg-card text-foreground ring-4 ring-beige-strong/40",
          !done && !current && overdue && "border-red-600 bg-background text-red-600",
          !done && !current && !overdue && "border-foreground/25 bg-background text-muted-foreground",
        )}
        aria-label={done ? "Đã xong" : `Mốc ${index}`}
      >
        {done ? <Check className="size-5" aria-hidden="true" /> : index}
      </span>

      <div className={cn("min-w-0", current && "rounded-xl border-2 border-beige-strong bg-card p-4")}>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className={cn("m-0 font-semibold", current ? "text-lg" : "text-base")}>{m.name}</h3>
              {current && <span className="rounded-full bg-foreground px-2.5 py-0.5 text-xs font-medium text-background">Chặng tiếp theo</span>}
            </div>
            <p className="m-0 mt-1 text-sm text-muted-foreground">
              {m.code} · Hạn {fmtDate(m.due_date)}
            </p>
          </div>
          <StatusBadge kind="milestone" value={m.status} />
        </div>

        {m.note && (
          <NoticeCard title="Nhận xét của giảng viên" className="mt-3">
            <p className="m-0 whitespace-pre-wrap">{m.note}</p>
          </NoticeCard>
        )}

        {(evidence.length > 0 || m.submittable) && (
          <div className="mt-3 space-y-2 text-sm">
            {evidence.length === 0 && <p className="m-0 text-muted-foreground">Chưa có minh chứng.</p>}
            {evidence.map((e, i) => {
              const failed = e.status === "rejected";
              return (
                <div key={e.id} className="flex items-start gap-2">
                <div className="min-w-0 flex-1 rounded-lg border border-foreground/15 bg-background px-3 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold">{i + 1}</span>
                      {e.filename ? (
                        <a href={`/api/evidence/${e.id}/download`} download className="inline-flex items-center gap-1.5 font-medium text-foreground no-underline hover:underline">
                          <FileText aria-hidden className="size-4 text-muted-foreground" />
                          Lần {i + 1}
                        </a>
                      ) : (
                        <span className="font-medium">Lần {i + 1}</span>
                      )}
                      <span className="text-xs text-muted-foreground">{fmtDateTime(e.submitted_at)}</span>
                    </div>
                    {failed ? <Badge tone="bad">Thất bại</Badge> : <StatusBadge kind="milestone" value={e.status} />}
                  </div>
                  {e.reviewer_comment && (
                    <p className={cn("m-0 mt-2 rounded-md px-2.5 py-1.5 text-xs", failed ? "bg-danger-soft text-destructive" : "bg-muted text-muted-foreground")}>
                      {failed ? "Lý do: " : "Nhận xét: "}
                      {e.reviewer_comment}
                    </p>
                  )}
                  {!failed && (
                    <div className="mt-2">
                      <EvidenceFieldsForm
                        key={`${e.id}-${autofill?.evidenceId === e.id ? autofillNonce : 0}-${autoExtractId === e.id ? 1 : 0}`}
                        evidence={e}
                        editable={working && !locked}
                        autofill={autofill?.evidenceId === e.id ? autofill : null}
                        autoExtract={autoExtractId === e.id}
                        onSaved={() => {
                          if (autofill?.evidenceId === e.id) onAutofillSaved();
                          reload();
                        }}
                      />
                    </div>
                  )}
                </div>
                {canWithdraw &&
                  (e.status === "submitted" ? (
                    // Nút dấu trừ nằm ngay bên phải dòng minh chứng (trong thẻ mốc), thẳng hàng với dòng đầu của nó.
                    <button
                      type="button"
                      aria-label={`Thu hồi Lần ${i + 1}`}
                      title="Thu hồi"
                      onClick={() => setWithdrawTarget({ id: e.id, n: i + 1 })}
                      className="mt-2.5 flex size-6 shrink-0 items-center justify-center rounded-full border-2 border-red-600 bg-background text-red-600 transition-colors hover:bg-red-600 hover:text-white"
                    >
                      <Minus aria-hidden className="size-3.5" strokeWidth={3} />
                    </button>
                  ) : (
                    <span aria-hidden className="size-6 shrink-0" />
                  ))}
                </div>
              );
            })}
          </div>
        )}
        <FormDialog title="Thu hồi minh chứng" open={withdrawTarget !== null} onOpenChange={(open) => !open && !withdraw.busy && setWithdrawTarget(null)}>
          <p className="m-0 text-sm">
            Thu hồi <strong>Lần {withdrawTarget?.n}</strong> của mốc {m.code}? Tệp sẽ bị xóa khỏi hệ thống và giảng viên không còn thấy nó. Bạn có thể tải lại tệp khác sau đó.
          </p>
          <ErrorText message={withdraw.error} />
          <div className="mt-4">
            <Row>
              <Button variant="danger" disabled={withdraw.busy} onClick={() => withdrawTarget && void withdraw.run(() => send("POST", `/api/student/evidence/${withdrawTarget.id}/withdraw`))}>
                {withdraw.busy ? "Đang thu hồi..." : "Thu hồi"}
              </Button>
              <Button disabled={withdraw.busy} onClick={() => setWithdrawTarget(null)}>
                Giữ lại
              </Button>
            </Row>
          </div>
        </FormDialog>
        {(up.error ?? submit.error) && (
          <NoticeCard tone="error" title="Có lỗi" className="mt-3">
            <p className="m-0">{up.error ?? submit.error}</p>
          </NoticeCard>
        )}

        {m.submittable && working && !locked && (
          <div className="mt-4">
            <Row>
              <FilePicker label="Tải minh chứng" accept=".pdf,.png,.jpg,.jpeg,.docx" disabled={up.busy} onFile={(file) => setPreviewFile(file)} />
              <EvidencePreviewDialog
                file={previewFile}
                busy={up.busy}
                onCancel={() => setPreviewFile(null)}
                onConfirm={() => {
                  const file = previewFile;
                  if (!file) return;
                  void uploadEvidence(file).then(() => setPreviewFile(null));
                }}
              />
              <Button variant="primary" disabled={submit.busy || evidence.filter((e) => e.status !== "rejected").length === 0} onClick={() => void submit.run(() => send("POST", `/api/student/milestones/${m.code}/submit`))}>
                Nộp mốc
              </Button>
              <Button onClick={() => setExtending((v) => !v)}>{extending ? "Đóng" : "Xin gia hạn"}</Button>
            </Row>
          </div>
        )}
        {working && !locked && !m.submittable && (
          <div className="mt-4">
            <Button onClick={() => setExtending((v) => !v)}>{extending ? "Đóng" : "Xin gia hạn"}</Button>
          </div>
        )}
        {extending && (
          <ExtensionForm
            milestone={m}
            onDone={() => {
              setExtending(false);
              reload();
            }}
          />
        )}
      </div>
    </li>
  );
}

function ExtensionForm({ milestone, onDone }: { milestone: Milestone; onDone: () => void }) {
  const [due, setDue] = useState("");
  const [reason, setReason] = useState("");
  const action = useAction(onDone);
  return (
    <div className="mt-4 rounded-lg border-2 border-beige-strong bg-background p-4">
      <Field label="Hạn mới đề nghị" required>
        <input type="date" value={due} min={milestone.due_date} onChange={(e) => setDue(e.target.value)} />
      </Field>
      <Field label="Lý do" required>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <ErrorText message={action.error} />
      <Button variant="primary" disabled={action.busy || !due || !reason.trim()} onClick={() => void action.run(() => send("POST", "/api/student/requests/extension", { milestone_code: milestone.code, new_due_date: due, reason }))}>
        Gửi yêu cầu gia hạn
      </Button>
    </div>
  );
}
