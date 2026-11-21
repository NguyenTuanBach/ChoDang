import type { ConversationSummary } from "@/lib/assistant-protocol";
import styles from "./assistant.module.css";

interface Props {
  conversations: ConversationSummary[];
  activeId: string | null;
  onNew: () => void;
  onOpen: (id: string) => void;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

export default function ConversationList({ conversations, activeId, onNew, onOpen }: Props) {
  return (
    <nav className={styles.sidebar} aria-label="Hội thoại">
      <button type="button" className={styles.primary} onClick={onNew}>
        Hội thoại mới
      </button>
      {conversations.length === 0 ? (
        <p className={styles.muted}>Chưa có hội thoại nào.</p>
      ) : (
        <ul className={styles.convList}>
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                className={conversation.id === activeId ? `${styles.conv} ${styles.convActive}` : styles.conv}
                aria-current={conversation.id === activeId ? "true" : undefined}
                onClick={() => onOpen(conversation.id)}
              >
                <span>{conversation.title || "Hội thoại chưa đặt tên"}</span>
                <small className={styles.muted}>{formatTime(conversation.updated_at)}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
