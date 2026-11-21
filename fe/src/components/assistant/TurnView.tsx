import type { Citation } from "@/lib/assistant-protocol";
import type { Turn } from "@/lib/assistant/reducer";
import Markdown from "./Markdown";
import { citationLabel } from "./citation";
import { DEGRADED_WARNING, ERROR_TEXT, SAMPLE_WARNING, STEP_LABEL, VERDICT_NOTE } from "./messages";
import styles from "./assistant.module.css";

interface Props {
  turn: Turn;
  onCite: (citation: Citation) => void;
  onReload: () => void;
}

// Một lượt hỏi-đáp: câu hỏi, tiến trình ("đang suy nghĩ"), câu trả lời, trích dẫn, cảnh báo, lỗi.
export default function TurnView({ turn, onCite, onReload }: Props) {
  const running = turn.phase === "running";
  const hasSample = turn.citations.some((citation) => citation.is_sample);
  const verdictNote = turn.verdict ? VERDICT_NOTE[turn.verdict] : undefined;

  return (
    <article className={styles.turn} data-phase={turn.phase}>
      <div className={styles.question}>{turn.question}</div>

      <div className={styles.answer}>
        {running && (
          <details className={styles.trace} open aria-label="Tiến trình xử lý">
            <summary>
              <span className={styles.spinner} aria-hidden="true" />
              {turn.cancelling ? "Đang dừng..." : turn.step ? STEP_LABEL[turn.step] : "Đang suy nghĩ..."}
            </summary>
            <ul>
              {turn.trace.map((item, index) => (
                <li key={index} className={item.ok === false ? styles.traceFail : undefined}>
                  {item.kind === "tool_call" && "Gọi: "}
                  {item.kind === "tool_result" && (item.ok ? "Xong: " : "Lỗi: ")}
                  {item.text}
                </li>
              ))}
            </ul>
          </details>
        )}

        {turn.text && <Markdown text={turn.text} citations={turn.citations} streaming={running} onCite={onCite} />}
        {running && turn.text && <span className={styles.caret} aria-hidden="true" />}

        {turn.degraded && (
          <p className={styles.warn} role="note">
            {DEGRADED_WARNING}
          </p>
        )}
        {hasSample && (
          <p className={styles.warn} role="note">
            {SAMPLE_WARNING}
          </p>
        )}
        {verdictNote && <p className={styles.info}>{verdictNote}</p>}

        {turn.citations.length > 0 && (
          <div className={styles.sources}>
            <span className={styles.muted}>Căn cứ:</span>
            {turn.citations.map((citation) => (
              <button
                key={citation.chunk_id}
                type="button"
                className={citation.is_sample ? `${styles.chip} ${styles.chipSample}` : styles.chip}
                title="Xem nguyên văn"
                onClick={() => onCite(citation)}
              >
                {citationLabel(citation)}
              </button>
            ))}
          </div>
        )}

        {turn.phase === "cancelled" && <p className={styles.info}>{ERROR_TEXT.cancelled}</p>}
        {turn.phase === "error" && turn.error && (
          <p className={styles.error} role="alert">
            {ERROR_TEXT[turn.error.code]}
            {turn.error.message && <small> ({turn.error.message})</small>}
          </p>
        )}
        {turn.phase === "interrupted" && (
          <p className={styles.info} role="status">
            Kết nối bị ngắt trước khi nhận đủ câu trả lời. Nếu hệ thống đã xử lý xong, câu trả lời sẽ hiện ở đây.{" "}
            <button type="button" className={styles.linkButton} onClick={onReload}>
              Tải lại
            </button>
          </p>
        )}
      </div>
    </article>
  );
}
