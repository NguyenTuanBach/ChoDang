"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Citation } from "@/lib/assistant-protocol";
import { useAssistant, type AssistantOptions } from "@/lib/assistant/useAssistant";
import CitationPanel from "./CitationPanel";
import ConversationList from "./ConversationList";
import TurnView from "./TurnView";
import { ERROR_TEXT } from "./messages";
import styles from "./assistant.module.css";

const CONNECTION_TEXT = {
  idle: "",
  connecting: "Đang kết nối...",
  ready: "Đã kết nối",
  reconnecting: "Mất kết nối, đang nối lại...",
  closed: "Chưa kết nối",
} as const;

export default function AssistantChat({ options }: { options?: AssistantOptions }) {
  const assistant = useAssistant(options);
  const { state } = assistant;
  const [draft, setDraft] = useState("");
  const [selected, setSelected] = useState<Citation | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const running = state.activeTurnId !== null;

  // Cuộn xuống cuối khi có nội dung mới.
  const lastText = state.turns.at(-1)?.text.length ?? 0;
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [state.turns.length, lastText]);

  function submit() {
    if (!draft.trim() || running) return;
    void assistant.ask(draft);
    setDraft("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className={styles.layout}>
      <ConversationList
        conversations={assistant.conversations}
        activeId={state.conversationId}
        onNew={() => {
          setSelected(null);
          assistant.newConversation();
        }}
        onOpen={(id) => {
          setSelected(null);
          void assistant.openConversation(id);
        }}
      />

      <section className={styles.main} aria-label="Trợ lý chính sách">
        <header className={styles.header}>
          <h1>Trợ lý chính sách thực tập</h1>
          <span className={styles.muted} role="status">
            {CONNECTION_TEXT[state.connection]}
          </span>
        </header>

        <div className={styles.thread} aria-live="polite">
          {state.turns.length === 0 ? (
            <p className={styles.muted}>
              Hỏi về quy chế thực tập, ví dụ: &quot;Hạn nộp đề cương là khi nào?&quot;. Câu trả lời luôn kèm căn cứ từ văn
              bản quy định; trợ lý chỉ cung cấp thông tin và không tự quyết định thay giảng viên hay nhà trường.
            </p>
          ) : (
            state.turns.map((turn) => (
              <TurnView key={turn.turnId} turn={turn} onCite={setSelected} onReload={() => void assistant.reload()} />
            ))
          )}
          <div ref={endRef} />
        </div>

        {state.notice && (
          <p className={styles.error} role="alert">
            {ERROR_TEXT[state.notice.code]}
            {state.notice.message && <small> ({state.notice.message})</small>}{" "}
            <button type="button" className={styles.linkButton} onClick={assistant.dismissNotice}>
              Ẩn
            </button>
          </p>
        )}

        <form
          className={styles.composer}
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Nhập câu hỏi (Enter để gửi, Shift+Enter xuống dòng)"
            aria-label="Câu hỏi"
            rows={2}
          />
          {running ? (
            <button type="button" className={styles.stop} onClick={assistant.cancel}>
              Dừng
            </button>
          ) : (
            <button type="submit" className={styles.primary} disabled={!draft.trim()}>
              Gửi
            </button>
          )}
        </form>
      </section>

      {selected && <CitationPanel citation={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
