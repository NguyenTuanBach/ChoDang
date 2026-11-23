"use client";

import { ChevronDown, ClipboardCheck, Plus, Sparkles, X } from "lucide-react";
import { useMemo, useState } from "react";
import CheckBox from "@/components/ui/check-box";
import { Async, Button, Empty, ErrorText, Page } from "@/components/ui/ui";
import { useAction, useApi } from "@/lib/hooks";
import { send } from "@/lib/http";
import { fmtDate, fmtDateTime } from "@/lib/labels";
import type { InternshipDetail, Journal, PlanItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const MIN_CONTENT = 20;

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// 17-11 (ngày-tháng) cho tiêu đề tuần.
function dayMonth(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${d}-${m}`;
}

const fieldLabel = "text-sm font-semibold";
const box = "rounded-xl border-2 border-foreground/25 bg-background";
// Ô nhập chữ: viền đen nhạt, cùng tông với các thẻ.
const card = "rounded-lg border-2 border-foreground/25 bg-background px-3 py-2.5";
const cardLabel = "mb-1 block text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
const field = "border-2 border-foreground/25";

export default function JournalPage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Nhật ký tuần">
      <Async state={state}>{(d) => <Content detail={d} reload={state.reload} />}</Async>
    </Page>
  );
}

function Content({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const row = detail.internship;
  if (!row) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;
  return (
    <>
      <Intro />
      {row.status === "in_progress" ? <Composer detail={detail} reload={reload} /> : <div className={cn(box, "p-4 text-sm")}>Bạn nộp được nhật ký khi hồ sơ ở trạng thái “Đang thực tập”.</div>}
      <History journals={detail.journals} reload={reload} />
    </>
  );
}

function Intro() {
  return (
    <div className={cn(box, "flex items-center gap-5 p-5")}>
      <div className="relative flex size-16 shrink-0 items-center justify-center rounded-2xl border-2 border-foreground/25 bg-background">
        <ClipboardCheck aria-hidden className="size-8" />
        <span className="absolute -bottom-1 -right-1 flex size-5 items-center justify-center rounded-full bg-green-600 text-white" aria-hidden>
          <svg viewBox="0 0 24 24" className="size-3" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12l5 5L20 7" />
          </svg>
        </span>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="m-0 text-xl font-semibold">Weekly standup</h2>
        </div>
        <p className="m-0 mt-1 text-sm text-muted-foreground">
          Bài nộp <strong className="text-foreground">cá nhân</strong>: mỗi bạn tự nộp mỗi tuần. Việc chưa xong tự chuyển sang tuần sau để bạn bổ sung.
        </p>
      </div>
    </div>
  );
}

type Item = PlanItem & { carried?: boolean };

function Composer({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const row = detail.internship!;
  const done = useMemo(() => new Set(detail.journals.map((j) => j.week_start)), [detail.journals]);
  // Các tuần đã bắt đầu mà chưa có nhật ký (tuần k bắt đầu ở start + 7k); mới nhất ở cuối.
  const open = useMemo(() => {
    if (!row.start_date) return [];
    const today = new Date().toISOString().slice(0, 10);
    const weeks: { value: string; n: number }[] = [];
    for (let k = 0; k < 40; k++) {
      const start = addDays(row.start_date, 7 * k);
      if (start > today || (row.end_date && start > row.end_date)) break;
      if (!done.has(start)) weeks.push({ value: start, n: k + 1 });
    }
    return weeks;
  }, [row, done]);

  // Việc chưa xong của nhật ký gần nhất được chuyển sang danh sách tuần này.
  const carried = useMemo<Item[]>(() => {
    const last = detail.journals[0];
    return (last?.plan_items ?? []).filter((i) => !i.done).map((i) => ({ text: i.text, done: false, carried: true }));
  }, [detail.journals]);

  const [week, setWeek] = useState("");
  const [content, setContent] = useState("");
  const [items, setItems] = useState<Item[] | null>(null);
  const [draft, setDraft] = useState("");
  const [blockers, setBlockers] = useState("");
  const [advice, setAdvice] = useState("");
  const list = items ?? carried;
  const selected = week || open[open.length - 1]?.value || "";

  const submit = useAction(() => {
    setContent("");
    setItems(null);
    setDraft("");
    setBlockers("");
    setAdvice("");
    setWeek("");
    reload();
  });
  const ask = useAction();

  if (open.length === 0) return <div className={cn(box, "p-4 text-sm")}>Bạn đã nộp nhật ký cho mọi tuần đã bắt đầu.</div>;

  const payloadItems = list.map(({ text, done: d }) => ({ text, done: d }));
  const number = open.find((w) => w.value === selected)?.n;
  const doneCount = list.filter((i) => i.done).length;

  const addItem = () => {
    const text = draft.trim();
    if (!text) return;
    setItems([...list, { text, done: false }]);
    setDraft("");
  };

  return (
    <div className="space-y-4">
      <div className={cn(box, "flex flex-wrap items-center justify-between gap-2 p-4")}>
        <div className="flex items-center gap-2">
          <h3 className="m-0 text-base font-semibold">
            Tuần {number} · {dayMonth(selected)}
          </h3>
          {open.length > 1 && (
            <select aria-label="Chọn tuần" value={selected} onChange={(e) => setWeek(e.target.value)} className={cn("h-8 py-0", field)}>
              {open.map((w) => (
                <option key={w.value} value={w.value}>
                  Tuần {w.n} (bắt đầu {fmtDate(w.value)})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className={cn(box, "space-y-5 p-5")}>
      <div>
        <div className="flex items-center justify-between">
          <label htmlFor="j-content" className={fieldLabel}>
            Tuần này: bạn đã làm gì?
          </label>
          <span className={cn("text-xs tabular-nums", content.trim().length >= MIN_CONTENT ? "text-green-700" : "text-muted-foreground")}>
            {content.trim().length}/{MIN_CONTENT}
          </span>
        </div>
        <textarea id="j-content" className={cn("mt-1.5 w-full", field)} value={content} onChange={(e) => setContent(e.target.value)} />
      </div>

      <div>
        <label htmlFor="j-blockers" className={fieldLabel}>
          Đang vướng (nếu có)
        </label>
        <textarea id="j-blockers" className={cn("mt-1.5 w-full", field)} placeholder="Bỏ trống nếu không vướng gì" value={blockers} onChange={(e) => setBlockers(e.target.value)} />
      </div>

      <div>
        <div className="flex items-center justify-between">
          <span className={fieldLabel}>Danh sách việc</span>
          {list.length > 0 && (
            <span className="text-xs tabular-nums text-muted-foreground">
              {doneCount}/{list.length} đã xong
            </span>
          )}
        </div>
        <p className="m-0 mt-0.5 text-xs text-muted-foreground">Tích việc đã hoàn thành. Việc chưa tích sẽ chuyển sang tuần sau để bổ sung.</p>
        {list.length > 0 && (
          <ul className="m-0 mt-2 list-none space-y-1.5 p-0">
            {list.map((it, idx) => (
              <li key={`${idx}-${it.text}`} className="flex items-center gap-2 rounded-lg border border-foreground/15 bg-background px-3 py-2">
                <CheckBox checked={it.done} onChange={(v) => setItems(list.map((x, i) => (i === idx ? { ...x, done: v } : x)))}>
                  {it.text}
                  {it.carried && <span className="ml-2 rounded-full border border-foreground/20 px-2 py-0.5 text-[11px] text-muted-foreground no-underline">Từ tuần trước</span>}
                </CheckBox>
                <button type="button" aria-label="Xóa việc" onClick={() => setItems(list.filter((_, i) => i !== idx))} className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                  <X aria-hidden className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-2 flex items-center gap-2">
          <input
            className={cn("min-w-0 flex-1", field)}
            placeholder="Thêm việc dự định cho tuần tới..."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addItem();
              }
            }}
          />
          <Button onClick={addItem} disabled={!draft.trim()}>
            <Plus aria-hidden className="size-4" />
            Thêm
          </Button>
        </div>
      </div>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <span className={fieldLabel}>Gợi ý lịch từ AI</span>
            <span className="inline-flex items-center gap-1 rounded-full border border-foreground/25 bg-secondary px-2 py-0.5 text-[11px] font-medium">
              <Sparkles aria-hidden className="size-3" />
              AI gợi ý
            </span>
          </span>
          <Button
            disabled={ask.busy || list.length === 0}
            onClick={() => void ask.run(async () => setAdvice((await send<{ advice: string }>("POST", "/api/student/journal/ai-advice", { content, plan_items: payloadItems, blockers })).advice))}
          >
            <Sparkles aria-hidden className="size-4" />
            {ask.busy ? "Đang hỏi AI..." : "Hỏi AI lịch đã ổn chưa"}
          </Button>
        </div>
        <div className="mt-1.5 rounded-lg border border-foreground/15 bg-background px-3 py-2.5 text-sm">
          {advice ? (
            <>
              <p className="m-0 whitespace-pre-wrap">{advice}</p>
              <button type="button" onClick={() => setAdvice("")} className="mt-2 text-xs text-muted-foreground hover:text-foreground">
                Bỏ gợi ý này
              </button>
            </>
          ) : (
            <span className="text-muted-foreground">Chưa hỏi AI. Không bắt buộc: thêm việc vào danh sách rồi bấm nút để nhận gợi ý, hoặc để trống.</span>
          )}
        </div>
        <ErrorText message={ask.error} />
      </div>

      <ErrorText message={submit.error} />
      <div className="flex justify-end">
        <Button
          variant="primary"
          disabled={submit.busy || content.trim().length < MIN_CONTENT || !selected}
          onClick={() => void submit.run(() => send("POST", "/api/student/journal", { week_start: selected, content, plan_items: payloadItems, blockers, ai_advice: advice }))}
        >
          Nộp nhật ký
        </Button>
      </div>
      </div>
    </div>
  );
}

function History({ journals, reload }: { journals: Journal[]; reload: () => void }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Các tuần gần nhất</h3>
      {journals.length === 0 ? (
        <Empty>Chưa có nhật ký.</Empty>
      ) : (
        <div className="space-y-3">
          {journals.map((j, i) => (
            <Entry key={j.id} journal={j} defaultOpen={i === 0} reload={reload} />
          ))}
        </div>
      )}
    </section>
  );
}

function Entry({ journal: j, defaultOpen, reload }: { journal: Journal; defaultOpen: boolean; reload: () => void }) {
  const [open, setOpen] = useState(defaultOpen);
  const toggle = useAction(reload);
  const items = j.plan_items ?? [];
  return (
    <div className={cn(box, "p-4")}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-start justify-between gap-3 text-left">
        <span>
          <span className="block text-base font-semibold">{dayMonth(j.week_start)}</span>
          <span className="block text-sm text-muted-foreground">Nộp lúc {fmtDateTime(j.submitted_at)}</span>
        </span>
        <span className="flex items-center gap-2">
          <ChevronDown aria-hidden className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-3 text-sm">
          <div className={card}>
            <span className={cardLabel}>Đã làm</span>
            <p className="m-0 whitespace-pre-wrap">{j.content}</p>
          </div>
          {j.blockers && (
            <div className={card}>
              <span className={cardLabel}>Đang vướng</span>
              <p className="m-0 whitespace-pre-wrap">{j.blockers}</p>
            </div>
          )}
          {items.length > 0 && (
            <div className={card}>
              <span className={cardLabel}>
                Danh sách việc · {items.filter((x) => x.done).length}/{items.length} đã xong
              </span>
              <ul className="m-0 mt-1 list-none space-y-1.5 p-0">
                {items.map((it, idx) => (
                  <li key={`${idx}-${it.text}`}>
                    <CheckBox
                      checked={it.done}
                      disabled={toggle.busy}
                      onChange={(v) => void toggle.run(() => send("PUT", `/api/student/journal/${j.id}/items`, { plan_items: items.map((x, i) => (i === idx ? { ...x, done: v } : x)) }))}
                    >
                      {it.text}
                    </CheckBox>
                  </li>
                ))}
              </ul>
              <ErrorText message={toggle.error} />
            </div>
          )}
          {j.lecturer_comment && (
            <div className={card}>
              <span className={cardLabel}>Nhận xét của giảng viên</span>
              <p className="m-0 whitespace-pre-wrap">{j.lecturer_comment}</p>
            </div>
          )}
          {j.ai_advice && (
            <div className={card}>
              <span className={cn(cardLabel, "inline-flex items-center gap-1")}>
                <Sparkles aria-hidden className="size-3" />
                AI gợi ý
              </span>
              <p className="m-0 whitespace-pre-wrap">{j.ai_advice}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
