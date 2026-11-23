"use client";

import { AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { useState } from "react";
import { Async, Button, Card, Empty, ErrorText, Field, Page, Pre, StatusBadge } from "@/components/ui/ui";
import { useAction, useApi } from "@/lib/hooks";
import { send } from "@/lib/http";
import { fmtDateTime } from "@/lib/labels";
import type { InternshipDetail, OutlineIssue, OutlineReview } from "@/lib/types";
import { cn } from "@/lib/utils";

const MIN_CHARS = 50;
const panel = "rounded-lg border-2 border-foreground/25 bg-background px-3 py-2.5 text-sm";

type SubmitResult = OutlineReview & { saved: boolean; id: number | null; outcome_codes: string[] };

export default function OutlinePage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Đề cương thực tập">
      <Async state={state}>{(d) => <Content detail={d} reload={state.reload} />}</Async>
    </Page>
  );
}

function Content({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const [content, setContent] = useState(detail.outlines[0]?.status === "revision_requested" ? detail.outlines[0].content : "");
  const [result, setResult] = useState<SubmitResult | null>(null);
  const submit = useAction();
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

  if (!row) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;

  return (
    <>
      <Card title={detail.outlines.length ? "Nộp phiên bản mới" : "Nộp đề cương"} className="bg-background">
        {!canSubmit && <p className={cn(panel, "mt-0")}>{blockedReason}</p>}
        <Field
          label="Nội dung đề cương"
          required
          hint="Gồm đủ bốn phần: Mục tiêu, Nhiệm vụ, Kế hoạch, Kết quả dự kiến (tối thiểu 50 ký tự). Khi nộp, hệ thống kiểm tra và AI nhận xét để bạn sửa. Chuẩn đầu ra do AI tự nhận diện."
        >
          <textarea value={content} disabled={!canSubmit} onChange={(e) => setContent(e.target.value)} style={{ minHeight: "14rem" }} />
        </Field>
        <ErrorText message={submit.error} />
        <Button
          variant="primary"
          disabled={!canSubmit || submit.busy || content.trim().length < MIN_CHARS}
          onClick={() =>
            void submit.run(async () => {
              const r = await send<SubmitResult>("POST", "/api/student/outlines", { content });
              setResult(r);
              if (r.saved) reload();
            })
          }
        >
          {submit.busy ? "Đang kiểm tra và nhờ AI nhận xét..." : "Nộp đề cương"}
        </Button>
        {submit.busy && <p className="mb-0 mt-2 text-sm text-muted-foreground">Việc này mất khoảng 10-30 giây.</p>}
      </Card>

      {result && <ResultCard result={result} />}

      <Card title="Các phiên bản đã nộp" className="bg-background">
        {detail.outlines.length === 0 && <Empty>Chưa nộp đề cương.</Empty>}
        <div className="space-y-3">
          {detail.outlines.map((o) => (
            <div key={o.id} className="rounded-lg border-2 border-foreground/25 bg-background p-3 text-sm">
              <p className="m-0 mb-2 flex flex-wrap items-center gap-2">
                <strong>Phiên bản {o.version}</strong> <StatusBadge kind="outline" value={o.status} /> <span className="text-muted-foreground">nộp {fmtDateTime(o.submitted_at)}</span>
              </p>
              <Pre>{o.content}</Pre>
              {o.outcome_codes.length > 0 && <p className="m-0 mt-2">Chuẩn đầu ra (AI nhận diện): <strong>{o.outcome_codes.join(", ")}</strong></p>}
              {o.ai_review && (o.ai_review.summary || (o.ai_review.issues?.length ?? 0) > 0) && (
                <div className="mt-2">
                  <AiReview review={o.ai_review} />
                </div>
              )}
              {o.feedback && <p className="m-0 mt-2">Phản hồi của giảng viên: {o.feedback}</p>}
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// Kết quả ngay sau khi bấm nộp: chưa nộp được (kèm chỗ sai theo từng phần) hoặc đã nộp (kèm gợi ý thêm của AI).
function ResultCard({ result }: { result: SubmitResult }) {
  const errors = result.issues.filter((i) => i.level === "error");
  return (
    <Card title={result.saved ? "Đã nộp đề cương" : "Chưa nộp được đề cương"} className="bg-background">
      {result.saved ? (
        <p className="m-0 mb-3 flex items-center gap-2 text-sm font-medium text-green-700">
          <CheckCircle2 aria-hidden className="size-4" /> Đề cương đã gửi giảng viên duyệt.
          {result.outcome_codes.length > 0 && <span className="font-normal text-foreground">Chuẩn đầu ra AI nhận diện: {result.outcome_codes.join(", ")}.</span>}
        </p>
      ) : (
        <>
          <p className="m-0 mb-2 text-sm">Đề cương còn chỗ chưa đạt. Hãy sửa các phần dưới đây rồi nộp lại.</p>
          <IssueList issues={errors} />
        </>
      )}
      <div className={errors.length > 0 ? "mt-3" : undefined}>
        <AiReview review={result} aiOnly />
      </div>
      {!result.ai && <p className="m-0 mt-2 text-sm text-muted-foreground">AI chưa nhận xét được lần này (agent chưa sẵn sàng). Việc kiểm tra các phần bắt buộc vẫn được thực hiện.</p>}
    </Card>
  );
}

function IssueList({ issues }: { issues: OutlineIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <ul className="m-0 list-none space-y-1.5 p-0" role="alert">
      {issues.map((i, idx) => (
        <li key={`${i.section}-${idx}`} className={cn("flex items-start gap-2 rounded-lg px-3 py-2 text-sm", i.level === "error" ? "bg-danger-soft text-destructive" : "bg-warning-soft text-warning")}>
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>
            <strong>{i.section}:</strong> {i.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

// Nhận xét của AI: tổng quát + các góp ý theo phần (chỉ góp ý, giảng viên mới duyệt).
function AiReview({ review, aiOnly }: { review: Partial<OutlineReview>; aiOnly?: boolean }) {
  const issues = (review.issues ?? []).filter((i) => (aiOnly ? i.level !== "error" : true));
  if (!review.summary && issues.length === 0) return null;
  return (
    <div className={panel}>
      <p className="m-0 mb-1.5 inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        <Sparkles aria-hidden className="size-3" /> Nhận xét của AI (chỉ để tham khảo)
      </p>
      {review.summary && <p className="m-0 whitespace-pre-wrap">{review.summary}</p>}
      {issues.length > 0 && (
        <div className="mt-2">
          <IssueList issues={issues} />
        </div>
      )}
    </div>
  );
}
