"use client";

import { ArrowUpRight, MoreHorizontal } from "lucide-react";
import { createContext, useContext, useState, type ReactNode } from "react";
import { FIELD_LABEL } from "@/lib/autofill";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { FLAG_KIND, MODE_LABEL, fmtDate, fmtDateTime } from "@/lib/labels";
import type { EvidenceExtraction, InternshipDetail, Milestone, Outline, Suggestion } from "@/lib/types";
import { Async, Badge, Button, Card, DecisionPanel, Empty, ErrorToast, Field, Page, Pre, Row, StatusBadge, Table } from "@/components/ui/ui";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import FormDialog from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import DownloadDoc from "@/components/student/DownloadDoc";
import { FlagActions } from "./FlagsPanel";
import { RequestDecision } from "./RequestsReview";

type Role = "lecturer" | "admin";

// Chi tiết một hồ sơ cho GV (xác nhận, duyệt, chấp nhận mốc, nhận xét, thẩm định) và QTV (xem, phê duyệt công nhận tín chỉ).
// Nhận xét bằng AI chỉ tồn tại trong lần mở trang này (không lưu lại để hiển thị): đổi trang hoặc tải lại là mất.
// BE vẫn ghi một bản để lưu vết, nhưng giao diện không đọc lại bản đó.
type AiReviewStore = { items: Suggestion[]; add: (s: Suggestion) => void };
const AiReviews = createContext<AiReviewStore>({ items: [], add: () => {} });

export default function InternshipDetailView({ id, role }: { id: number; role: Role }) {
  const state = useApi<InternshipDetail>(`/api/internships/${id}`);
  const [items, setItems] = useState<Suggestion[]>([]);
  const add = (s: Suggestion) => setItems((prev) => [s, ...prev.filter((x) => !(x.subject_kind === s.subject_kind && x.subject_id === s.subject_id))]);
  return (
    <AiReviews.Provider value={{ items, add }}>
      <Page title="Hồ sơ thực tập">
        <Async state={state}>{(d) => <Body d={d} role={role} reload={state.reload} />}</Async>
      </Page>
    </AiReviews.Provider>
  );
}

type Pending = { kind: string; run: (reason: string) => Promise<unknown>; label: string; needReason: boolean; danger?: boolean } | null;

function Body({ d, role, reload }: { d: InternshipDetail; role: Role; reload: () => void }) {
  const row = d.internship;
  const { items: aiItems } = useContext(AiReviews);
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  if (!row) return <Empty>Không có dữ liệu.</Empty>;
  const isLecturer = role === "lecturer";
  const ask = (p: NonNullable<Pending>) => setPending(p);

  return (
    <>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="m-0 text-xl font-bold tracking-tight">{row.student_name}</h2>
            <p className="m-0 mt-1 text-sm text-muted-foreground">
              {row.student_code ?? row.student_email} · Khóa {row.cohort} · Giảng viên: {row.lecturer_name ?? "—"}
            </p>
          </div>
          <StatusBadge kind="internship" value={row.status} />
        </div>
        <dl className="m-0 mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Doanh nghiệp</dt>
            <dd className="m-0 mt-1 text-sm font-medium">{row.company_name || "Chưa khai báo"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Bắt đầu</dt>
            <dd className="m-0 mt-1 text-sm font-medium">{fmtDate(row.start_date)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Kết thúc</dt>
            <dd className="m-0 mt-1 text-sm font-medium">{fmtDate(row.end_date)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Hình thức</dt>
            <dd className="m-0 mt-1 text-sm font-medium">{MODE_LABEL[row.mode]}</dd>
          </div>
        </dl>
        {row.decision_reason && <p className="mb-0 mt-4 text-sm">Lý do quyết định gần nhất: {row.decision_reason}</p>}
        <div className="mt-5 border-t border-foreground/15 pt-5">
          <dl className="m-0 grid grid-cols-[8.5rem_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="font-medium text-muted-foreground">MST · Địa chỉ</dt>
            <dd className="m-0">
              {row.company_tax_code} · {row.company_address}
            </dd>
            <dt className="font-medium text-muted-foreground">Vị trí</dt>
            <dd className="m-0">
              {row.position}
              {row.department && ` · ${row.department}`}
            </dd>
            <dt className="font-medium text-muted-foreground">Người hướng dẫn</dt>
            <dd className="m-0">
              {row.mentor_name}
              {row.mentor_title && ` (${row.mentor_title})`} · {row.mentor_email} · {row.mentor_phone}
            </dd>
            {(row.receipt_letter_number || row.receipt_signer_name) && (
              <>
                <dt className="font-medium text-muted-foreground">Giấy tiếp nhận</dt>
                <dd className="m-0">
                  {[row.receipt_letter_number && `Số ${row.receipt_letter_number}`, row.receipt_letter_date && `ngày ${fmtDate(row.receipt_letter_date)}`, row.receipt_signer_name && `ký: ${row.receipt_signer_name}${row.receipt_signer_title ? ` (${row.receipt_signer_title})` : ""}`]
                    .filter(Boolean)
                    .join(" · ")}
                </dd>
              </>
            )}
            <dt className="font-medium text-muted-foreground">Mô tả công việc</dt>
            <dd className="m-0 whitespace-pre-wrap break-words">{row.job_description}</dd>
          </dl>
          {Object.values(row.field_confirmations).includes("ai_confirmed") && <p className="mb-0 mt-3"><small>Các trường do AI gợi ý và sinh viên đã xác nhận: {Object.entries(row.field_confirmations).filter(([, v]) => v === "ai_confirmed").map(([k]) => FIELD_LABEL[k] ?? k).join(", ")}</small></p>}
          {/* Mỗi hồ sơ chỉ có một giấy tiếp nhận: dữ liệu cũ còn nhiều giấy thì chỉ hiện giấy mới nhất. */}
          {d.documents.slice(-1).map((doc) => (
            <div key={doc.id} className="mt-2">
              <DownloadDoc href={`/api/documents/${doc.id}/download`} name={doc.filename} />
            </div>
          ))}
        </div>
        {isLecturer && row.status === "submitted" && (
          <div className="mt-3">
          <Row>
            <Button variant="primary" onClick={() => ask({ kind: "i", label: "Xác nhận hồ sơ", needReason: false, run: () => send("POST", `/api/internships/${row.id}/decision`, { action: "confirm" }) })}>
              Xác nhận hồ sơ
            </Button>
            <Button onClick={() => ask({ kind: "i", label: "Yêu cầu sửa", needReason: true, run: (reason) => send("POST", `/api/internships/${row.id}/decision`, { action: "request_revision", reason }) })}>
              Yêu cầu sửa
            </Button>
            <Button variant="danger" onClick={() => ask({ kind: "i", label: "Từ chối hồ sơ", needReason: true, danger: true, run: (reason) => send("POST", `/api/internships/${row.id}/decision`, { action: "reject", reason }) })}>
              Từ chối
            </Button>
          </Row>
          </div>
        )}
        {pending?.kind === "i" && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
      </Card>

      {d.credit && <CreditCard d={d} role={role} reload={reload} />}

      <Card title="Đề cương">
        {d.outlines.length === 0 && <Empty>Chưa nộp đề cương.</Empty>}
        {d.outlines.map((o) => (
          <OutlineBlock key={o.id} outline={o} d={d} isLecturer={isLecturer} reload={reload} />
        ))}
      </Card>

      {d.outlines.some((o) => aiItems.some((sg) => sg.subject_kind === "outline" && sg.subject_id === o.id)) && (
        <Card title="Nhận xét của AI về đề cương">
          <p className="m-0 mb-3 text-xs text-muted-foreground">Nhận xét chỉ hiển thị trong lần xem này; đổi trang hoặc tải lại sẽ không còn.</p>
          {d.outlines.map((o) => {
            const items = aiItems.filter((sg) => sg.subject_kind === "outline" && sg.subject_id === o.id);
            return items.length === 0 ? null : (
              <div key={o.id} className="mb-4 last:mb-0">
                <p className="m-0 text-sm font-medium">Phiên bản {o.version}</p>
                <Suggestions items={items} />
              </div>
            );
          })}
        </Card>
      )}

      <Card title="Mốc">
        <Table head={["Mốc", "Hạn", "Trạng thái", "Minh chứng", "Cập nhật", "Cảnh báo", ""]}>
          {d.milestones.map((m) => (
            <MilestoneRow key={m.id} m={m} d={d} isLecturer={isLecturer} reload={reload} />
          ))}
        </Table>
      </Card>

      {d.journals.length === 0 ? (
        <Card title="Nhật ký tuần">
          <Empty>Chưa có nhật ký.</Empty>
        </Card>
      ) : (
        <>
          <h2 className="m-0 text-lg font-semibold">Nhật ký tuần</h2>
          {d.journals.map((j) => (
            <JournalBlock key={j.id} j={j} isLecturer={isLecturer} reload={reload} />
          ))}
        </>
      )}

      <Card title="Yêu cầu gia hạn / ngoại lệ">
        {d.requests.length === 0 && <Empty>Không có yêu cầu.</Empty>}
        {d.requests.map((r) => {
          const mine = r.status === "open" && ((isLecturer && !r.affects_credit) || (!isLecturer && r.affects_credit));
          return (
            <div key={r.id} style={{ marginBottom: "0.75rem" }}>
              <Row>
                <StatusBadge kind="request" value={r.status} />
                <strong>{r.kind === "milestone_extension" ? `Gia hạn ${r.milestone_code} (hạn mới ${fmtDate(r.new_due_date)})` : r.exception_type_name}</strong>
                {r.affects_credit && <Badge tone="warn">Ảnh hưởng tín chỉ</Badge>}
              </Row>
              <p>Lý do: {r.reason}</p>
              {r.decision_reason && <p>Phản hồi: {r.decision_reason}</p>}
              {r.attachments.map((a) => (
                <div key={a.id}>
                  <DownloadDoc href={`/api/request-attachments/${a.id}/download`} name={a.filename} />
                </div>
              ))}
              {mine && <RequestDecision item={r} reload={reload} />}
            </div>
          );
        })}
      </Card>

      <Card title="Cờ rủi ro">
        {d.flags.length === 0 && <Empty>Không có cờ.</Empty>}
        <div className="space-y-3">
          {d.flags.map((f) => (
            <div key={f.id} className="flex items-start justify-between gap-4 rounded-lg border-2 border-foreground/15 px-4 py-3">
              <div className="min-w-0 flex-1">
                <Row>
                  <StatusBadge kind="severity" value={f.severity} />
                  <StatusBadge kind="flag" value={f.status} />
                  <strong>{FLAG_KIND[f.kind] ?? f.kind}</strong>
                  <Badge>{f.created_by_kind === "agent" ? "Do AI đề xuất" : "Do hệ thống phát hiện"}</Badge>
                </Row>
                <p className="mb-0 mt-2 text-sm">{f.reason}</p>
                {f.suggestion && <p className="mb-0 mt-1 text-sm text-muted-foreground">Gợi ý: {f.suggestion}</p>}
              </div>
              <FlagActions flag={f} reload={reload} />
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function Decision({ pending, action, onCancel }: { pending: NonNullable<Pending>; action: ReturnType<typeof useAction>; onCancel: () => void }) {
  return (
    <DecisionPanel
      confirmLabel={pending.label}
      requireReason={pending.needReason}
      variant={pending.danger ? "danger" : "primary"}
      busy={action.busy}
      error={action.error}
      onCancel={onCancel}
      onSubmit={(reason) => void action.run(() => pending.run(reason))}
    />
  );
}

// Gợi ý của AI (tiền thẩm): luôn gắn nhãn, không có nút nào để AI quyết định thay giảng viên.
function Suggestions({ items }: { items: Suggestion[] }) {
  if (items.length === 0) return null;
  const s = items[0];
  return (
    <div style={{ borderLeft: "3px solid #b45309", paddingLeft: "0.75rem", margin: "0.5rem 0" }}>
      <Badge tone="warn">Gợi ý của AI — không thay quyết định của giảng viên</Badge> <small>{fmtDateTime(s.created_at)}</small>
      <Pre>{s.summary}</Pre>
      {s.details.outcome_matches && s.details.outcome_matches.length > 0 && (
        <ul>
          {s.details.outcome_matches.map((m) => (
            <li key={m.code}>
              {m.code}: {m.covered ? "có phủ" : "chưa thấy phủ"} — {m.note}
            </li>
          ))}
        </ul>
      )}
      {s.details.concerns && s.details.concerns.length > 0 && (
        <>
          <strong>Điểm cần lưu ý</strong>
          <ul>
            {s.details.concerns.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}
      {s.details.evidence_notes && s.details.evidence_notes.length > 0 && (
        <>
          <strong>Về minh chứng</strong>
          <ul>
            {s.details.evidence_notes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

// Nhận xét bằng AI (gợi ý, không quyết định thay giảng viên): gọi BE rồi tải lại; lỗi hiện toast.
function useAiReview(internshipId: number, kind: "outline" | "milestone", subjectId: number) {
  const { add } = useContext(AiReviews);
  const action = useAction();
  const run = () =>
    void action.run(async () => {
      const result = await send<Omit<Suggestion, "created_at">>("POST", `/api/internships/${internshipId}/pre-review`, { subject_kind: kind, subject_id: subjectId });
      add({ ...result, created_at: new Date().toISOString() });
    });
  return { busy: action.busy, error: action.error, run };
}

function PreReviewButton({ internshipId, kind, subjectId }: { internshipId: number; kind: "outline" | "milestone"; subjectId: number }) {
  const ai = useAiReview(internshipId, kind, subjectId);
  return (
    <>
      <Button variant="primary" disabled={ai.busy} onClick={ai.run}>
        {ai.busy ? "AI đang đọc..." : "Nhận xét bằng AI"}
      </Button>
      <ErrorToast title="Không lấy được nhận xét của AI" message={ai.error} />
    </>
  );
}

function OutlineBlock({ outline: o, d, isLecturer, reload }: { outline: Outline; d: InternshipDetail; isLecturer: boolean; reload: () => void }) {
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  const id = d.internship?.id ?? 0;
  const ai = useAiReview(id, "outline", o.id);
  const decide = (p: NonNullable<Pending>) => setPending(p);
  return (
    <div className="mb-4 last:mb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Row>
          <strong>Phiên bản {o.version}</strong>
          <StatusBadge kind="outline" value={o.status} />
          <span className="text-sm text-muted-foreground">{fmtDateTime(o.submitted_at)}</span>
        </Row>
        {o.status === "submitted" && (
          <div className="flex items-center gap-2">
            {ai.busy && <span className="text-sm text-muted-foreground">AI đang đọc...</span>}
            <ErrorToast title="Không lấy được nhận xét của AI" message={ai.error} />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label="Thao tác"
                  disabled={ai.busy}
                  className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg border-2 border-foreground/25 bg-card text-foreground shadow-xs hover:bg-secondary disabled:opacity-50"
                >
                  <MoreHorizontal className="size-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => ai.run()}>Nhận xét bằng AI</DropdownMenuItem>
                {isLecturer && (
                  <>
                    <DropdownMenuItem onSelect={() => decide({ kind: "o", label: "Duyệt đề cương", needReason: false, run: () => send("POST", `/api/outlines/${o.id}/decision`, { action: "approve" }) })}>Duyệt</DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => decide({ kind: "o", label: "Yêu cầu sửa", needReason: true, run: (reason) => send("POST", `/api/outlines/${o.id}/decision`, { action: "request_revision", reason }) })}>Yêu cầu sửa</DropdownMenuItem>
                  <DropdownMenuItem variant="destructive" onSelect={() => decide({ kind: "o", label: "Từ chối đề cương", needReason: true, danger: true, run: (reason) => send("POST", `/api/outlines/${o.id}/decision`, { action: "reject", reason }) })}>
                    Từ chối
                  </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>
      <div className="mt-3">
        <Pre>{o.content}</Pre>
        {o.file_name && (
          <div className="mt-2">
            <DownloadDoc href={`/api/outlines/${o.id}/file`} name={o.file_name} />
          </div>
        )}
      </div>
      {o.feedback && <p className="mb-0 mt-3 text-sm">Phản hồi: {o.feedback}</p>}
      {pending && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
    </div>
  );
}

function MilestoneRow({ m, d, isLecturer, reload }: { m: Milestone; d: InternshipDetail; isLecturer: boolean; reload: () => void }) {
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  // Chỉ hiện minh chứng gần nhất của mốc; thời điểm cập nhật = lúc duyệt nếu đã duyệt, không thì lúc nộp.
  const updatedAt = (e: InternshipDetail["evidence"][number]) => e.reviewed_at ?? e.submitted_at;
  const latest = d.evidence.filter((e) => e.milestone_code === m.code).sort((a, b) => updatedAt(b).localeCompare(updatedAt(a)))[0];
  const suggestions = useContext(AiReviews).items.filter((s) => s.subject_kind === "milestone" && s.subject_id === m.id);
  const id = d.internship?.id ?? 0;
  const [detailOpen, setDetailOpen] = useState(false);
  const extraction = latest?.extraction;
  return (
    <>
      {extraction && (
        <FormDialog title={`${m.code} — ${m.name}`} wide open={detailOpen} onOpenChange={setDetailOpen}>
          <ExtractionBlock extraction={extraction} />
        </FormDialog>
      )}
      <tr
        // Bấm vào dòng mốc (không phải liên kết hay nút bên trong) thì mở popup chi tiết nếu mốc có thông tin trên giấy.
        className={extraction ? "cursor-pointer" : undefined}
        tabIndex={extraction ? 0 : undefined}
        onClick={extraction ? (e) => !(e.target as HTMLElement).closest("a, button, [role=menuitem]") && setDetailOpen(true) : undefined}
        onKeyDown={extraction ? (e) => e.target === e.currentTarget && (e.key === "Enter" || e.key === " ") && setDetailOpen(true) : undefined}
      >
        <td>
          {m.code} — {m.name}
        </td>
        <td>{fmtDate(m.due_date)}</td>
        <td>
          <StatusBadge kind="milestone" value={m.status} />
          {m.note && <div>{m.note}</div>}
        </td>
        <td>
          {latest ? (
            latest.filename ? (
              <a href={`/api/evidence/${latest.id}/download`} download title={latest.title || latest.filename} aria-label="Mở minh chứng" className="inline-flex items-center gap-1 no-underline">
                <StatusBadge kind="milestone" value={latest.status} />
                <ArrowUpRight className="size-4 text-muted-foreground" aria-hidden="true" />
              </a>
            ) : (
              <StatusBadge kind="milestone" value={latest.status} />
            )
          ) : (
            "—"
          )}
        </td>
        <td className="whitespace-nowrap">{latest ? fmtDateTime(updatedAt(latest)) : "—"}</td>
        <td>
          {extraction ? extraction.mismatches.length > 0 ? <Badge tone="bad">{extraction.mismatches.length} cảnh báo</Badge> : <span className="text-sm text-muted-foreground">Không có</span> : "—"}
        </td>
        <td>
          {m.stored_status === "submitted" && (
            <Row>
              <PreReviewButton internshipId={id} kind="milestone" subjectId={m.id} />
              {isLecturer && (
                <>
                  <Button variant="primary" onClick={() => setPending({ kind: "m", label: "Chấp nhận mốc", needReason: false, run: () => send("POST", `/api/milestones/${m.id}/accept`) })}>
                    Chấp nhận
                  </Button>
                  <Button variant="danger" onClick={() => setPending({ kind: "m", label: "Trả lại mốc", needReason: true, danger: true, run: (reason) => send("POST", `/api/milestones/${m.id}/reject`, { reason }) })}>
                    Trả lại
                  </Button>
                </>
              )}
            </Row>
          )}
        </td>
      </tr>
      {(pending || suggestions.length > 0) && (
        <tr>
          <td colSpan={7}>
            <Suggestions items={suggestions} />
            {pending && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
          </td>
        </tr>
      )}

    </>
  );
}

// Thông tin SV đã xác nhận từ giấy xác nhận / phiếu đánh giá (M5) và các chỗ lệch với hồ sơ mà BE phát hiện. GV vẫn cần mở tệp gốc để xác thực.
function ExtractionBlock({ extraction }: { extraction: EvidenceExtraction }) {
  const entries = Object.entries(extraction.fields);
  return (
    <div className="mb-3 rounded-lg border-2 border-beige-strong bg-background p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <strong className="text-base">Thông tin trên giấy</strong>
        <span className="text-sm text-muted-foreground">Sinh viên xác nhận lúc {fmtDateTime(extraction.confirmed_at)}</span>
      </div>
      <dl className="m-0 mt-4 grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
        {entries.map(([key, value]) => (
          <div key={key} className="min-w-0">
            <dt className="text-sm text-muted-foreground">{FIELD_LABEL[key] ?? key}</dt>
            <dd className="m-0 mt-1 whitespace-pre-wrap break-words text-base font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      {extraction.mismatches.length > 0 && (
        <div className="mt-5 space-y-2 border-t border-foreground/15 pt-4" role="alert">
          <p className="m-0 text-sm font-medium text-muted-foreground">Cần kiểm tra</p>
          {extraction.mismatches.map((m) => (
            <div key={m.field + m.label} className="rounded-lg border-2 border-destructive/40 bg-danger-soft px-3 py-2 text-sm text-destructive">
              <strong>{m.label}</strong>
              <div className="mt-0.5">{m.detail}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Mỗi tuần một card, mỗi mục có nhãn riêng: việc đã làm, việc dự kiến (kèm đã/chưa xong), đang vướng, gợi ý AI, nhận xét.
function JournalRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-t border-foreground/15 py-3 first:border-t-0 first:pt-0 sm:grid-cols-[9rem_1fr] sm:gap-4">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="m-0 min-w-0 whitespace-pre-wrap break-words text-sm leading-relaxed">{children}</dd>
    </div>
  );
}

function JournalBlock({ j, isLecturer, reload }: { j: InternshipDetail["journals"][number]; isLecturer: boolean; reload: () => void }) {
  const [comment, setComment] = useState("");
  const action = useAction(() => {
    setComment("");
    reload();
  });
  const items = j.plan_items ?? [];
  const doneCount = items.filter((it) => it.done).length;
  return (
    <Card title={`Tuần bắt đầu ${fmtDate(j.week_start)}`} actions={items.length > 0 ? <span className="text-sm text-muted-foreground">Hoàn thành {doneCount}/{items.length} việc</span> : undefined}>
      <dl className="m-0">
        <JournalRow label="Việc đã làm">{j.content}</JournalRow>
        {items.length > 0 && (
          <JournalRow label="Kế hoạch tuần tới">
            <ul className="m-0 list-none space-y-1.5 p-0">
              {items.map((it, i) => (
                <li key={`${i}-${it.text}`} className="flex items-start gap-2">
                  <span className={cn("mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded border-2 text-[10px] font-bold leading-none", it.done ? "border-green-600 bg-green-600 text-white" : "border-foreground/30 bg-background text-transparent")}>✓</span>
                  <span className={it.done ? "text-muted-foreground" : undefined}>{it.text}</span>
                </li>
              ))}
            </ul>
          </JournalRow>
        )}
        {j.blockers && <JournalRow label="Đang vướng">{j.blockers}</JournalRow>}
        {j.ai_advice && (
          <JournalRow label="Gợi ý lịch từ AI">
            {j.ai_advice}
            <div className="mt-1 text-xs text-muted-foreground">Sinh viên tự hỏi AI khi viết nhật ký.</div>
          </JournalRow>
        )}
        {j.lecturer_comment && <JournalRow label="Nhận xét của giảng viên">{j.lecturer_comment}</JournalRow>}
      </dl>
      {isLecturer && (
        <div className="mt-4 border-t border-foreground/15 pt-4">
          <Field label={j.lecturer_comment ? "Cập nhật nhận xét" : "Nhận xét"}>
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} style={{ minHeight: "3rem" }} />
          </Field>
          <ErrorToast title="Không gửi được nhận xét" message={action.error} />
          <Button variant="primary" disabled={action.busy || !comment.trim()} onClick={() => void action.run(() => send("POST", `/api/journal/${j.id}/comment`, { comment }))}>
            Gửi nhận xét
          </Button>
        </div>
      )}
    </Card>
  );
}

// Kết quả thẩm định tín chỉ: nhãn tiếng Việt, đạt/được công nhận màu xanh lá, trả lại/không công nhận màu đỏ.
const ASSESSMENT_LABEL: Record<string, string> = {
  pending: "Đang thẩm định",
  lecturer_passed: "Giảng viên thẩm định đạt, chờ quản trị viên",
  lecturer_returned: "Giảng viên trả lại",
  approved: "Được công nhận",
  denied: "Không công nhận",
};
const ASSESSMENT_TONE: Record<string, "good" | "warn" | "bad"> = { pending: "warn", lecturer_passed: "good", lecturer_returned: "bad", approved: "good", denied: "bad" };

function CreditCard({ d, role, reload }: { d: InternshipDetail; role: Role; reload: () => void }) {
  const row = d.internship;
  const credit = d.credit;
  const [pending, setPending] = useState<Pending>(null);
  const action = useAction(() => {
    setPending(null);
    reload();
  });
  if (!row || !credit) return null;
  return (
    <Card title="Điều kiện công nhận tín chỉ (T1–T6)">
      <Table head={["Mã", "Điều kiện", "Hiện tại", "Ngưỡng", ""]}>
        {credit.items.map((i) => (
          <tr key={i.code}>
            <td>{i.code}</td>
            <td>{i.label}</td>
            <td>{i.value}</td>
            <td>{i.threshold}</td>
            <td>
              <Badge tone={i.met ? "good" : "warn"}>{i.met ? "Đạt" : "Chưa đạt"}</Badge>
            </td>
          </tr>
        ))}
      </Table>
      {credit.assessment && (
        <div className="mt-4 rounded-lg border-2 border-foreground/15 bg-background px-4 py-3">
          <dl className="m-0 grid grid-cols-[9rem_1fr] items-start gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Kết quả thẩm định</dt>
            <dd className="m-0">
              <Badge tone={ASSESSMENT_TONE[credit.assessment.status] ?? "neutral"}>{ASSESSMENT_LABEL[credit.assessment.status] ?? credit.assessment.status}</Badge>
            </dd>
            {credit.assessment.lecturer_note && (
              <>
                <dt className="text-muted-foreground">Ghi chú giảng viên</dt>
                <dd className="m-0 whitespace-pre-wrap break-words">{credit.assessment.lecturer_note}</dd>
              </>
            )}
            {credit.assessment.admin_reason && (
              <>
                <dt className="text-muted-foreground">Quản trị viên</dt>
                <dd className="m-0 whitespace-pre-wrap break-words">{credit.assessment.admin_reason}</dd>
              </>
            )}
          </dl>
        </div>
      )}
      {role === "lecturer" && row.status === "pending_credit" && (
        <div className="mt-4">
        <Row>
          <Button variant="primary" disabled={!credit.all_met} onClick={() => setPending({ kind: "c", label: "Thẩm định đạt, chuyển QTV", needReason: false, run: (note) => send("POST", `/api/internships/${row.id}/credit/assess`, { passed: true, note }) })}>
            Thẩm định đạt
          </Button>
          <Button variant="danger" onClick={() => setPending({ kind: "c", label: "Trả hồ sơ lại cho sinh viên", needReason: true, danger: true, run: (note) => send("POST", `/api/internships/${row.id}/credit/assess`, { passed: false, note }) })}>
            Trả lại sinh viên
          </Button>
          {!credit.all_met && <small className="text-muted-foreground">Chỉ thẩm định đạt khi mọi điều kiện đạt (hãy chấp nhận mốc M3–M5 trước).</small>}
        </Row>
        </div>
      )}
      {role === "admin" && row.status === "credit_review" && (
        <div className="mt-4">
        <Row>
          <Button variant="primary" onClick={() => setPending({ kind: "c", label: "Phê duyệt công nhận (ghi LMS)", needReason: false, run: (reason) => send("POST", `/api/internships/${row.id}/credit/decision`, { approve: true, reason }) })}>
            Phê duyệt công nhận
          </Button>
          <Button variant="danger" onClick={() => setPending({ kind: "c", label: "Không công nhận", needReason: true, danger: true, run: (reason) => send("POST", `/api/internships/${row.id}/credit/decision`, { approve: false, reason }) })}>
            Không công nhận
          </Button>
        </Row>
        </div>
      )}
      {pending && <Decision pending={pending} action={action} onCancel={() => setPending(null)} />}
    </Card>
  );
}
