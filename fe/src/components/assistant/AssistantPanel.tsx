"use client";

import { Check, History, Plus, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import type { Citation } from "@/lib/assistant-protocol";
import { cn } from "@/lib/utils";
import { useAssistantContext } from "./AssistantProvider";
import AutofillCards from "./AutofillCard";
import ChatThread from "./ChatThread";
import CitationPanel from "./CitationPanel";
import Composer from "./Composer";
import { formatTime } from "./ConversationList";
import { ERROR_TEXT } from "./messages";

export const CONNECTION_TEXT = {
  idle: "",
  connecting: "Đang kết nối...",
  ready: "Đã kết nối",
  reconnecting: "Mất kết nối, đang nối lại...",
  closed: "Chưa kết nối",
} as const;

// Ngăn Trợ lý gọn: tiêu đề + trạng thái kết nối + chọn/mới hội thoại, luồng chat, ô nhập. Trích dẫn mở thay luồng chat (có nút Đóng).
export default function AssistantPanel({ onClose }: { onClose?: () => void }) {
  const { assistant, canAttach, attachDocument } = useAssistantContext();
  const { state } = assistant;
  const [selected, setSelected] = useState<Citation | null>(null);
  const running = state.activeTurnId !== null;

  return (
    <section className="flex h-full min-h-0 flex-col" aria-label="Trợ lý thực tập">
      <header className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Sparkles className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="m-0 truncate text-sm font-semibold">Trợ lý thực tập</h2>
          <p className="m-0 flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
            <span className={cn("size-1.5 rounded-full", state.connection === "ready" ? "bg-success" : "bg-muted-foreground/50")} aria-hidden="true" />
            {CONNECTION_TEXT[state.connection] || "Sẵn sàng"}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Hội thoại">
              <History className="size-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-h-80 w-72 overflow-y-auto">
            <DropdownMenuItem
              onSelect={() => {
                setSelected(null);
                assistant.newConversation();
              }}
            >
              <Plus className="size-4" /> Hội thoại mới
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs text-muted-foreground">Hội thoại gần đây</DropdownMenuLabel>
            {assistant.conversations.length === 0 && <p className="m-0 px-2 py-1.5 text-sm text-muted-foreground">Chưa có hội thoại nào.</p>}
            {assistant.conversations.map((conversation) => (
              <DropdownMenuItem
                key={conversation.id}
                onSelect={() => {
                  setSelected(null);
                  void assistant.openConversation(conversation.id);
                }}
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate">{conversation.title || "Hội thoại chưa đặt tên"}</span>
                  <span className="text-xs text-muted-foreground">{formatTime(conversation.updated_at)}</span>
                </span>
                {conversation.id === state.conversationId && <Check className="size-4 text-primary" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Hội thoại mới"
          onClick={() => {
            setSelected(null);
            assistant.newConversation();
          }}
        >
          <Plus className="size-4" />
        </button>
        {onClose && (
          <button type="button" className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Đóng Trợ lý" onClick={onClose}>
            <X className="size-4" />
          </button>
        )}
      </header>

      {selected ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <CitationPanel citation={selected} onClose={() => setSelected(null)} />
        </div>
      ) : (
        <ChatThread assistant={assistant} onCite={setSelected} />
      )}

      {state.notice && (
        <p className="m-0 mx-3 mb-2 rounded-lg border border-destructive/40 bg-danger-soft px-3 py-2 text-sm text-destructive" role="alert">
          {ERROR_TEXT[state.notice.code]}
          {state.notice.message && <small> ({state.notice.message})</small>}{" "}
          <button type="button" className="text-primary underline" onClick={assistant.dismissNotice}>
            Ẩn
          </button>
        </p>
      )}

      <AutofillCards />
      <Composer compact running={running} onSend={(text) => void assistant.ask(text)} onStop={assistant.cancel} onAttach={canAttach ? attachDocument : undefined} />
    </section>
  );
}
