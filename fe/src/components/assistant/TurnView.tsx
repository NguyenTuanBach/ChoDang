import { Loader2, MoveRight } from "lucide-react";
import Link from "next/link";
import type { Citation } from "@/lib/assistant-protocol";
import type { Turn } from "@/lib/assistant/reducer";
import Markdown from "./Markdown";
import { CHIP_CLASS, CHIP_SAMPLE_CLASS, citationLabel } from "./citation";
import { DEGRADED_WARNING, ERROR_TEXT, SAMPLE_WARNING, STEP_LABEL, VERDICT_NOTE } from "./messages";

interface Props {
  turn: Turn;
  onCite: (citation: Citation) => void;
  onReload: () => void;
  // Trang mà trợ lý đã mở trong lượt này (đã đổi sang URL theo vai trò), hiện dưới câu trả lời để người dùng thấy và quay lại.
  openedPages?: { href: string; label: string }[];
}

const NOTE = "mt-2 rounded-lg border px-3 py-2 text-sm";

// Một lượt hỏi-đáp: câu hỏi, tiến trình ("đang suy nghĩ"), câu trả lời, trích dẫn, cảnh báo, lỗi.
export default function TurnView({ turn, onCite, onReload, openedPages = [] }: Props) {
  const running = turn.phase === "running";
  const hasSample = turn.citations.some((citation) => citation.is_sample);
  const verdictNote = turn.verdict ? VERDICT_NOTE[turn.verdict] : undefined;

  return (
    <article className="flex flex-col gap-2" data-phase={turn.phase}>
      <div className="max-w-[85%] self-end whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">{turn.question}</div>

      <div className="max-w-full break-words">
        {running && (
          <details className="mb-2 text-sm text-muted-foreground" open aria-label="Tiến trình xử lý">
            <summary className="flex cursor-pointer items-center gap-2">
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              {turn.cancelling ? "Đang dừng..." : turn.step ? STEP_LABEL[turn.step] : "Đang suy nghĩ..."}
            </summary>
            <ul className="mb-0 mt-1.5 list-disc pl-5">
              {turn.trace.map((item, index) => (
                <li key={index} className={item.ok === false ? "text-destructive" : undefined}>
                  {item.kind === "tool_call" && "Gọi: "}
                  {item.kind === "tool_result" && (item.ok ? "Xong: " : "Lỗi: ")}
                  {item.text}
                </li>
              ))}
            </ul>
          </details>
        )}

        {turn.text && <Markdown text={turn.text} citations={turn.citations} streaming={running} onCite={onCite} />}
        {running && turn.text && <span className="inline-block h-4 w-2 animate-pulse bg-muted-foreground align-text-bottom" aria-hidden="true" />}

        {turn.degraded && (
          <p className={`${NOTE} border-warning/40 bg-warning-soft text-warning`} role="note">
            {DEGRADED_WARNING}
          </p>
        )}
        {hasSample && (
          <p className={`${NOTE} border-warning/40 bg-warning-soft text-warning`} role="note">
            {SAMPLE_WARNING}
          </p>
        )}
        {verdictNote && <p className={`${NOTE} border-border bg-muted`}>{verdictNote}</p>}

        {openedPages.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-sm">
            {openedPages.map((page) => (
              <Link key={page.href} href={page.href} className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground hover:bg-accent/70">
                <MoveRight className="size-3" aria-hidden="true" />
                Đã mở: {page.label}
              </Link>
            ))}
          </div>
        )}

        {turn.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            <span className="text-sm text-muted-foreground">Căn cứ:</span>
            {turn.citations.map((citation) => (
              <button
                key={citation.chunk_id}
                type="button"
                className={citation.is_sample ? CHIP_SAMPLE_CLASS : CHIP_CLASS}
                title="Xem nguyên văn"
                onClick={() => onCite(citation)}
              >
                {citationLabel(citation)}
              </button>
            ))}
          </div>
        )}

        {turn.phase === "cancelled" && <p className={`${NOTE} border-border bg-muted`}>{ERROR_TEXT.cancelled}</p>}
        {turn.phase === "error" && turn.error && (
          <p className={`${NOTE} border-destructive/40 bg-danger-soft text-destructive`} role="alert">
            {ERROR_TEXT[turn.error.code]}
            {turn.error.message && <small> ({turn.error.message})</small>}
          </p>
        )}
        {turn.phase === "interrupted" && (
          <p className={`${NOTE} border-border bg-muted`} role="status">
            Kết nối bị ngắt trước khi nhận đủ câu trả lời. Nếu hệ thống đã xử lý xong, câu trả lời sẽ hiện ở đây.{" "}
            <button type="button" className="text-primary underline" onClick={onReload}>
              Tải lại
            </button>
          </p>
        )}
      </div>
    </article>
  );
}
