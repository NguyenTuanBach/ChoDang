"use client";

import { useState } from "react";
import type { Citation } from "@/lib/assistant-protocol";
import { useAssistantContext } from "./AssistantProvider";
import { CONNECTION_TEXT } from "./AssistantPanel";
import ChatThread from "./ChatThread";
import CitationPanel from "./CitationPanel";
import Composer from "./Composer";
import ConversationList from "./ConversationList";
import { ERROR_TEXT } from "./messages";

// Trang /assistant toàn màn hình: danh sách hội thoại bên trái, luồng chat ở giữa, nguyên văn trích dẫn bên phải.
// Dùng chung phiên với ngăn Trợ lý (cùng AssistantProvider), nên hội thoại đang mở ở ngăn sẽ hiện ở đây.
export default function AssistantChat() {
  const { assistant } = useAssistantContext();
  const { state } = assistant;
  const [selected, setSelected] = useState<Citation | null>(null);
  const running = state.activeTurnId !== null;

  return (
    <div className={`grid h-[calc(100svh-3.5rem-1rem)] min-h-0 grid-cols-1 ${selected ? "md:grid-cols-[240px_minmax(0,1fr)_340px]" : "md:grid-cols-[240px_minmax(0,1fr)]"}`}>
      <div className="hidden min-h-0 md:block">
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
      </div>

      <section className="flex min-h-0 min-w-0 flex-col" aria-label="Trợ lý chính sách">
        <header className="flex items-baseline justify-between gap-4 border-b border-border px-5 py-3">
          <h1 className="m-0 text-lg font-semibold">Trợ lý chính sách thực tập</h1>
          <span className="text-sm text-muted-foreground" role="status">
            {CONNECTION_TEXT[state.connection]}
          </span>
        </header>

        <ChatThread assistant={assistant} onCite={setSelected} />

        {state.notice && (
          <p className="m-0 mx-5 mb-2 rounded-lg border border-destructive/40 bg-danger-soft px-3 py-2 text-sm text-destructive" role="alert">
            {ERROR_TEXT[state.notice.code]}
            {state.notice.message && <small> ({state.notice.message})</small>}{" "}
            <button type="button" className="text-primary underline" onClick={assistant.dismissNotice}>
              Ẩn
            </button>
          </p>
        )}

        <Composer running={running} onSend={(text) => void assistant.ask(text)} onStop={assistant.cancel} />
      </section>

      {selected && (
        <div className="hidden min-h-0 border-l border-border md:block">
          <CitationPanel citation={selected} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  );
}
