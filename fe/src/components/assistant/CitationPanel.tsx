import type { Citation } from "@/lib/assistant-protocol";
import { SAMPLE_WARNING } from "./messages";
import { citationLabel } from "./citation";
import styles from "./assistant.module.css";

interface Props {
  citation: Citation;
  onClose: () => void;
}

// Panel xem nguyên văn điều/khoản được trích. `quote` hiển thị dạng văn bản thuần.
export default function CitationPanel({ citation, onClose }: Props) {
  return (
    <aside className={styles.panel} aria-label="Nguyên văn trích dẫn">
      <div className={styles.panelHead}>
        <strong>{citationLabel(citation)}</strong>
        <button type="button" className={styles.linkButton} onClick={onClose} aria-label="Đóng nguyên văn">
          Đóng
        </button>
      </div>
      <p className={styles.muted}>
        {citation.doc_title} · phiên bản {citation.version} · hiệu lực từ {citation.effective_from}
      </p>
      {citation.is_sample && (
        <p className={styles.warn} role="note">
          {SAMPLE_WARNING}
        </p>
      )}
      <blockquote className={styles.quote}>{citation.quote}</blockquote>
    </aside>
  );
}
