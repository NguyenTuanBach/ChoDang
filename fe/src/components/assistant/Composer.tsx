"use client";

import { Paperclip, SendHorizontal, Square } from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface Props {
  running: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  compact?: boolean;
  // Có thì hiện nút đính kèm giấy (PDF, ảnh chụp, bản scan) để AI đọc và tự điền.
  onAttach?: (file: File) => void;
}

// Ô nhập câu hỏi: Enter gửi, Shift+Enter xuống dòng (không gửi khi đang gõ tiếng Việt bằng bộ gõ).
export default function Composer({ running, onSend, onStop, compact = false, onAttach }: Props) {
  const [draft, setDraft] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  function submit() {
    if (!draft.trim() || running) return;
    onSend(draft);
    setDraft("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      className={cn("flex items-end gap-2 border-t border-border bg-card", compact ? "p-3" : "px-5 py-3")}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {onAttach && (
        <>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onAttach(file);
              event.target.value = "";
            }}
          />
          <button
            type="button"
            className="inline-flex size-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Đính kèm giấy tiếp nhận / giấy xác nhận để AI tự điền"
            title="Đính kèm giấy (PDF, ảnh) để AI tự điền"
            onClick={() => fileInput.current?.click()}
          >
            <Paperclip className="size-4" aria-hidden="true" />
          </button>
        </>
      )}
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Nhập câu hỏi (Enter để gửi, Shift+Enter xuống dòng)"
        aria-label="Câu hỏi"
        rows={2}
        className="min-h-0 flex-1 resize-none"
      />
      {running ? (
        <button type="button" className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-destructive px-3 text-sm font-medium text-white hover:bg-destructive/90" onClick={onStop}>
          <Square className="size-3.5 fill-current" aria-hidden="true" />
          Dừng
        </button>
      ) : (
        <button
          type="submit"
          className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-sm font-medium text-primary-foreground shadow-xs hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!draft.trim()}
        >
          <SendHorizontal className="size-4" aria-hidden="true" />
          Gửi
        </button>
      )}
    </form>
  );
}
