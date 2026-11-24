"use client";

import { AlertTriangle, FileText, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import NoticeCard from "@/components/ui/notice-card";
import { Async, Button, Card, Empty, ErrorText, FilePicker, Page, Pre, StatusBadge } from "@/components/ui/ui";
import { usePendingAutofill, type PendingAutofill } from "@/lib/autofill";
import { useAction, useApi } from "@/lib/hooks";
import { send, upload } from "@/lib/http";
import { fmtDateTime } from "@/lib/labels";
import { composeOutline, EMPTY_SECTIONS, parseOutline, SECTIONS, type SectionKey, type SectionValues } from "@/lib/outline-sections";
import type { InternshipDetail, OutlineIssue, OutlineReview } from "@/lib/types";
import { cn } from "@/lib/utils";
import DownloadDoc from "./DownloadDoc";
import EvidencePreviewDialog from "./EvidencePreviewDialog";

const MIN_CHARS = 50;
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.docx,.txt,.md";
// Loại tệp lưu được kèm đề cương (txt/md chỉ để AI đọc, không lưu).
const STORABLE = /\.(pdf|png|jpe?g|docx)$/i;
const panel = "rounded-lg border-2 border-foreground/25 bg-background px-3 py-2.5 text-sm";

type ExtractResult = { fields: Partial<Record<SectionKey, { value: string }>>; notes: string };
type SubmitResult = OutlineReview & { saved: boolean; id: number | null; outcome_codes: string[] };

export default function OutlinePage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  // Đề cương đính kèm trong ngăn Trợ lý: AI đã tách bốn phần, điền nháp vào form (chưa nộp). `nonce` làm key để dựng lại form khi có tệp mới.
  const auto = usePendingAutofill("outline", state.reload);
  return (
    <Page title="Đề cương thực tập">
      <Async state={state}>{(d) => <Content key={auto.nonce} detail={d} reload={state.reload} autofill={auto.value} />}</Async>
    </Page>
  );
}

function Content({ detail, reload, autofill }: { detail: InternshipDetail; reload: () => void; autofill: PendingAutofill | null }) {
  const [values, setValues] = useState<SectionValues>(() => {
    const base = parseOutline(detail.outlines[0]?.status === "revision_requested" ? detail.outlines[0].content : "");
    if (!autofill) return base;
    // Chỉ ghi đè các phần AI đọc được; phần khác giữ như cũ.
    for (const sec of SECTIONS) if (autofill.fields[sec.key]?.value) base[sec.key] = autofill.fields[sec.key].value;
    return base;
  });
  const content = composeOutline(values);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const submit = useAction();
  // Tệp đề cương vừa chọn (chờ xem lại), kết quả AI điền từ tệp, và hành động đọc tệp.
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  // Tệp đã đọc, sẽ được lưu kèm đề cương khi nộp thành công.
  const [attached, setAttached] = useState<File | null>(null);
  const [filled, setFilled] = useState<{ count: number; notes: string } | null>(() => (autofill ? { count: Object.keys(autofill.fields).length, notes: "" } : null));
  const read = useAction();
  const row = detail.internship;
  const pending = detail.outlines.some((o) => o.status === "submitted");
  const canSubmit = row?.status === "confirmed" && !pending;
  // Lý do chưa nộp được (form vẫn hiện nhưng khóa): đề cương chỉ nộp khi giảng viên đã xác nhận hồ sơ và chưa có bản đang chờ duyệt.
  const blockedReason =
    row?.status === "draft" || row?.status === "submitted" || row?.status === "revision_requested"
      ? "Bạn nộp được đề cương sau khi giảng viên xác nhận hồ sơ."
      : pending
        ? "Đề cương đang chờ giảng viên duyệt."
        : "Đề cương không cần nộp thêm ở trạng thái hiện tại.";

  const labels = new Set<string>(SECTIONS.map((x) => x.label));
  const fieldIssues: Record<string, OutlineIssue[]> = {};
  if (result && !result.saved) {
    for (const issue of result.issues) {
      if (labels.has(issue.section)) (fieldIssues[issue.section] ??= []).push(issue);
    }
  }

  if (!row) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;

  return (
    <>
      <Card
        title={detail.outlines.length ? "Nộp phiên bản mới" : "Nộp đề cương"}
        className="bg-background"
        actions={<FilePicker label={read.busy ? "AI đang đọc tệp..." : "Tải tệp đề cương"} accept={ACCEPT} disabled={!canSubmit || read.busy} onFile={(file) => setPreviewFile(file)} />}
      >
        {!canSubmit && <p className={cn(panel, "mt-0")}>{blockedReason}</p>}
        {attached && (
          <div className="mb-4 inline-flex max-w-full items-center gap-2 rounded-lg border border-foreground/25 bg-background px-3 py-2 text-sm font-medium">
            <FileText aria-hidden className="size-4 shrink-0" />
            <span className="truncate">{attached.name}</span>
            <button type="button" aria-label="Bỏ tệp đính kèm" className="shrink-0 text-muted-foreground hover:text-foreground" onClick={() => setAttached(null)}>
              <X aria-hidden className="size-4" />
            </button>
          </div>
        )}
        <EvidencePreviewDialog
          title="Xem lại tệp đề cương"
          file={previewFile}
          busy={read.busy}
          onCancel={() => setPreviewFile(null)}
          onConfirm={() => {
            const file = previewFile;
            if (!file) return;
            void read
              .run(async () => {
                const r = await upload<ExtractResult>("/api/student/outlines/extract", file);
                // Chỉ điền các phần AI đọc được; phần khác giữ nguyên để không mất chữ đã nhập.
                setValues((v) => ({ ...v, ...Object.fromEntries(SECTIONS.filter((x) => r.fields[x.key]?.value).map((x) => [x.key, r.fields[x.key]!.value])) }));
                setFilled({ count: Object.keys(r.fields).length, notes: r.notes });
                setAttached(STORABLE.test(file.name) ? file : null);
                setResult(null);
              })
              .then(() => setPreviewFile(null));
          }}
        />
        {read.error && (
          <div className="mb-4">
            <NoticeCard tone="error" title="Không đọc được tệp">
              <p className="m-0">{read.error}</p>
            </NoticeCard>
          </div>
        )}
        {filled && (
          <div className="mb-4">
            <NoticeCard tone={filled.count > 0 ? "info" : "warning"} title={filled.count > 0 ? `AI đã điền ${filled.count}/${SECTIONS.length} phần từ tệp` : "AI không tách được phần nào từ tệp"}>
              <p className="m-0">{filled.count > 0 ? "Hãy kiểm tra và sửa các ô trước khi nộp." : "Hãy nhập tay vào các ô bên dưới."}{filled.notes ? ` ${filled.notes}` : ""}</p>
            </NoticeCard>
          </div>
        )}
        <div className="space-y-4">
          {SECTIONS.map((sec) => {
            const issues = fieldIssues[sec.label] ?? [];
            const hasError = issues.some((i) => i.level === "error");
            return (
              <div key={sec.key}>
                <label htmlFor={`outline-${sec.key}`} className="text-sm font-semibold">
                  {sec.label}
                  <span className="ml-0.5 text-destructive" aria-hidden="true">
                    *
                  </span>
                </label>
                <textarea
                  id={`outline-${sec.key}`}
                  className={cn("mt-1.5 block w-full border-2", hasError ? "border-red-600" : "border-foreground/25")}
                  rows={4}
                  placeholder={sec.placeholder}
                  value={values[sec.key]}
                  disabled={!canSubmit}
                  onChange={(e) => setValues((v) => ({ ...v, [sec.key as SectionKey]: e.target.value }))}
                />
                {issues.length > 0 && (
                  <ul className="m-0 mt-1.5 list-none space-y-1 p-0" role="alert">
                    {issues.map((i, idx) => (
                      <li key={idx} className={cn("flex items-start gap-1.5 text-sm", i.level === "error" ? "text-destructive" : "text-muted-foreground")}>
                        <AlertTriangle aria-hidden className={cn("mt-0.5 size-4 shrink-0", i.level === "error" ? "text-red-600" : "text-amber-600")} />
                        <span>{i.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
        {submit.error && (
          <div className="mt-4">
            <ErrorText message={submit.error} />
          </div>
        )}
        {/* Cách các trường 16px (bằng khoảng cách giữa các trường), đồng đều với lề trong của thẻ. */}
        <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
          <Button
            variant="primary"
            disabled={!canSubmit || submit.busy || content.trim().length < MIN_CHARS}
            onClick={() =>
              void submit.run(async () => {
                const r = await send<SubmitResult>("POST", "/api/student/outlines", { content });
                setResult(r);
                if (r.saved) {
                  // Lưu bản gốc tệp đã tải kèm phiên bản vừa nộp; lỗi lưu tệp không làm mất lần nộp.
                  if (attached && r.id) {
                    await upload(`/api/student/outlines/${r.id}/file`, attached).catch((e: unknown) => toast.error(`Đã nộp nhưng chưa lưu được tệp đính kèm: ${e instanceof Error ? e.message : "lỗi không rõ"}`));
                    setAttached(null);
                  }
                  // Đã nộp: xóa nội dung vừa nộp khỏi form (bản đã nộp xem ở "Các phiên bản đã nộp").
                  setValues({ ...EMPTY_SECTIONS });
                  setFilled(null);
                  reload();
                }
              })
            }
          >
            {submit.busy ? "Đang kiểm tra và nhờ AI nhận xét..." : "Nộp đề cương"}
          </Button>
        </div>
      </Card>

      {result && <ResultCard result={result} inlineLabels={labels} />}

      <Card title="Các phiên bản đã nộp" className="bg-background">
        {detail.outlines.length === 0 && <Empty>Chưa nộp đề cương.</Empty>}
        <div className="space-y-5">
          {detail.outlines.map((o) => {
            const hasAi = Boolean(o.ai_review && (o.ai_review.summary || (o.ai_review.issues?.length ?? 0) > 0));
            return (
              <div key={o.id} className="space-y-3">
                <div className={cn(panel, "p-3")}>
                  <p className="m-0 mb-2 flex flex-wrap items-center gap-2">
                    <strong>Phiên bản {o.version}</strong> <StatusBadge kind="outline" value={o.status} /> <span className="text-muted-foreground">nộp {fmtDateTime(o.submitted_at)}</span>
                  </p>
                  <Pre>{o.content}</Pre>
                  {o.file_name && (
                    <div className="mt-3">
                      <DownloadDoc href={`/api/outlines/${o.id}/file`} name={o.file_name} />
                    </div>
                  )}
                </div>
                {(hasAi || o.feedback) && (
                  <section className={cn(panel, "p-0")}>
                    <header className="border-b border-foreground/15 px-4 py-2.5 font-semibold">Nhận xét · Phiên bản {o.version}</header>
                    <div className="space-y-4 px-4 py-3">
                      {o.feedback && (
                        <div>
                          <p className={blockLabel}>Giảng viên</p>
                          <p className="m-0 whitespace-pre-wrap leading-relaxed">{o.feedback}</p>
                        </div>
                      )}
                      {hasAi && <AiReview review={o.ai_review!} bare />}
                    </div>
                  </section>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </>
  );
}

// Kết quả ngay sau khi bấm nộp: chưa nộp được (kèm chỗ cần sửa) hoặc đã nộp (kèm nhận xét thêm của AI). Các khối cách đều nhau.
function ResultCard({ result, inlineLabels }: { result: SubmitResult; inlineLabels: Set<string> }) {
  // Lỗi gắn với một trường đã hiện ngay dưới trường đó; ở đây chỉ giữ lỗi chung (độ dài, chuẩn đầu ra...).
  const errors = result.issues.filter((i) => i.level === "error" && !(!result.saved && inlineLabels.has(i.section)));
  const review = { ...result, issues: result.issues.filter((i) => result.saved || !inlineLabels.has(i.section)) };
  const hasReview = Boolean(review.summary) || review.issues.some((i) => i.level !== "error");
  // Nộp thành công: báo bằng toast; thẻ chỉ giữ lại khi còn nhận xét của AI hoặc cảnh báo để xem.
  useEffect(() => {
    if (result.saved) toast.success("Đã nộp đề cương, đã gửi giảng viên duyệt.");
  }, [result]);
  if (result.saved && !hasReview && errors.length === 0) return null;
  return (
    <Card title={result.saved ? "Nhận xét sau khi nộp" : "Chưa nộp được đề cương"} className="bg-background">
      <div className="space-y-3">
        {errors.length > 0 && <IssueBlock title="Cần sửa trước khi nộp" tone="error" issues={errors} />}
        {hasReview && <AiReview review={review} aiOnly />}
        {!result.ai && <p className="m-0 text-sm text-muted-foreground">AI chưa nhận xét được lần này (agent chưa sẵn sàng). Việc kiểm tra các phần bắt buộc vẫn được thực hiện.</p>}
      </div>
    </Card>
  );
}

const blockLabel = "m-0 mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";

// Danh sách chỗ cần sửa / góp ý: mỗi dòng một nhãn phần (chip) bên trái và nội dung bên phải, các dòng ngăn bằng đường kẻ mảnh.
function IssueRows({ issues, tone }: { issues: OutlineIssue[]; tone: "error" | "warning" }) {
  return (
    <ul className="m-0 list-none divide-y divide-foreground/10 p-0">
      {issues.map((i, idx) => (
        <li key={`${i.section}-${idx}`} className="grid grid-cols-1 gap-1.5 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[8.5rem_1fr] sm:gap-3">
          <span
            className={cn(
              "h-fit w-fit rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              tone === "error" ? "border-red-600/40 bg-danger-soft text-destructive" : "border-foreground/25 bg-secondary text-foreground",
            )}
          >
            {i.section}
          </span>
          <span className="leading-relaxed">{i.message}</span>
        </li>
      ))}
    </ul>
  );
}

// Khối có vạch màu bên trái (đỏ = cần sửa), tiêu đề kèm số mục.
function IssueBlock({ title, tone, issues }: { title: string; tone: "error" | "warning"; issues: OutlineIssue[] }) {
  return (
    <section role={tone === "error" ? "alert" : undefined} className={cn("rounded-xl border-2 border-l-4 border-foreground/25 bg-background px-4 py-3 text-sm", tone === "error" ? "border-l-red-600" : "border-l-amber-500")}>
      <p className="m-0 mb-2.5 flex items-center gap-2 font-semibold">
        <AlertTriangle aria-hidden className={cn("size-4", tone === "error" ? "text-red-600" : "text-amber-600")} />
        {title} <span className="font-normal text-muted-foreground">({issues.length})</span>
      </p>
      <IssueRows issues={issues} tone={tone} />
    </section>
  );
}

// Nhận xét của AI: tổng quan rồi các góp ý theo phần (chỉ để tham khảo, giảng viên mới duyệt).
function AiReview({ review, aiOnly, bare }: { review: Partial<OutlineReview>; aiOnly?: boolean; bare?: boolean }) {
  const issues = (review.issues ?? []).filter((i) => (aiOnly ? i.level !== "error" : true));
  if (!review.summary && issues.length === 0) return null;
  const pad = bare ? "" : "px-4 py-3";
  return (
    <section className={bare ? "text-sm" : "rounded-xl border-2 border-foreground/25 bg-background text-sm"}>
      <header className={cn("flex items-center justify-between gap-2", bare ? "mb-2" : "border-b border-foreground/15 px-4 py-2.5")}>
        <span className={cn("inline-flex items-center gap-2", bare ? "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground" : "font-semibold")}>
          <Sparkles aria-hidden className="size-4" /> {bare ? "AI nhận xét" : "Nhận xét của AI"}
        </span>
        <span className="text-xs text-muted-foreground">Chỉ để tham khảo</span>
      </header>
      {review.summary && (
        <div className={pad}>
          <p className={blockLabel}>Tổng quan</p>
          <p className="m-0 whitespace-pre-wrap leading-relaxed">{review.summary}</p>
        </div>
      )}
      {issues.length > 0 && (
        <div className={cn(pad, review.summary && (bare ? "mt-3 border-t border-foreground/10 pt-3" : "border-t border-foreground/15"))}>
          <p className={blockLabel}>
            Góp ý theo phần <span className="font-normal normal-case">({issues.length})</span>
          </p>
          <IssueRows issues={issues} tone="warning" />
        </div>
      )}
    </section>
  );
}
