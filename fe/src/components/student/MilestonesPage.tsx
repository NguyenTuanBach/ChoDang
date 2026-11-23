"use client";

import { Check } from "lucide-react";
import { useState } from "react";
import AutofillPrompt from "@/components/shared/AutofillPrompt";
import { usePendingAutofill, type PendingAutofill } from "@/lib/autofill";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate } from "@/lib/labels";
import type { InternshipDetail, Milestone } from "@/lib/types";
import { Async, Button, Card, Empty, ErrorText, Field, FilePicker, Page, Row, StatusBadge } from "@/components/ui/ui";
import { cn } from "@/lib/utils";
import DownloadDoc from "./DownloadDoc";
import EvidenceFieldsForm from "./EvidenceFieldsForm";

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

function dueText(m: Milestone): string {
  const base = `Hạn ${fmtDate(m.due_date)}`;
  if (m.stored_status === "accepted") return base;
  if (m.days_left < 0) return `${base} · quá ${-m.days_left} ngày`;
  if (m.days_left === 0) return `${base} · hôm nay`;
  return `${base} · còn ${m.days_left} ngày`;
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
  const evidence = detail.evidence.filter((e) => e.milestone_code === m.code);
  const working = ["in_progress", "pending_credit"].includes(detail.internship?.status ?? "");
  const locked = m.stored_status === "submitted" || m.stored_status === "accepted";
  const done = m.stored_status === "accepted";
  const overdue = !done && m.days_left < 0;
  const up = useAction(reload);
  const submit = useAction(reload);
  const [extending, setExtending] = useState(false);
  const [prompt, setPrompt] = useState<number | null>(null);
  const [autoExtractId, setAutoExtractId] = useState<number | null>(null);
  const isCompletion = m.code === COMPLETION_CODE;

  async function uploadEvidence(file: File) {
    let id: number | null = null;
    const ok = await up.run(async () => {
      id = (await upload<{ id: number }>(`/api/student/milestones/${m.code}/evidence`, file)).id;
    });
    if (ok && id !== null && isCompletion && /\.(pdf|png|jpe?g)$/i.test(file.name)) setPrompt(id);
  }

  return (
    <li className={cn("relative grid grid-cols-[2.5rem_1fr] gap-x-4", !last && "pb-8")}>
      {!last && <span aria-hidden="true" className={cn("absolute bottom-0 left-5 top-10 w-0 -translate-x-1/2 border-l-2", done ? "border-solid border-green-600" : "border-dashed border-beige-strong")} />}
      <span
        className={cn(
          "relative z-10 flex size-10 items-center justify-center rounded-full border-2 text-sm font-semibold",
          done && "border-green-600 bg-green-600 text-white",
          !done && current && "border-foreground bg-foreground text-background ring-4 ring-beige-strong",
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
            <p className={cn("m-0 mt-1 text-sm", overdue ? "font-medium text-red-600" : "text-muted-foreground")}>
              {m.code} · {dueText(m)}
            </p>
          </div>
          <StatusBadge kind="milestone" value={m.status} />
        </div>

        {m.next_action && !done && <p className="m-0 mt-2 text-sm">{m.next_action}</p>}
        {m.note && <p className="m-0 mt-2 text-sm text-muted-foreground">Nhận xét của giảng viên: {m.note}</p>}

        {(evidence.length > 0 || m.submittable) && (
          <div className="mt-3 space-y-2 text-sm">
            {evidence.length === 0 && <p className="m-0 text-muted-foreground">Chưa có minh chứng.</p>}
            {evidence.map((e) => (
              <div key={e.id} className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Đã tải:</span>
                {e.filename ? <DownloadDoc href={`/api/evidence/${e.id}/download`} name={e.title || e.filename} /> : <span>{e.title}</span>}
                <StatusBadge kind="milestone" value={e.status} />
                {e.reviewer_comment && <span className="text-muted-foreground">— {e.reviewer_comment}</span>}
                {isCompletion && e.status !== "rejected" && (
                  <div className="basis-full">
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
            ))}
          </div>
        )}
        <ErrorText message={up.error ?? submit.error} />

        {m.submittable && working && !locked && (
          <div className="mt-4">
            <Row>
              <FilePicker label="Tải minh chứng" accept=".pdf,.png,.jpg,.jpeg,.docx" disabled={up.busy} onFile={(file) => void uploadEvidence(file)} />
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
        <AutofillPrompt
          open={prompt !== null}
          onYes={() => {
            setAutoExtractId(prompt);
            setPrompt(null);
          }}
          onNo={() => setPrompt(null)}
        />
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
