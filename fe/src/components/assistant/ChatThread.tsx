"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Citation } from "@/lib/assistant-protocol";
import type { AssistantApi } from "@/lib/assistant/useAssistant";
import { pageHref } from "@/lib/nav";
import { useCurrentUser } from "@/lib/user-context";
import TurnView from "./TurnView";
import { SUGGESTIONS } from "./suggestions";

interface Props {
  assistant: AssistantApi;
  onCite: (citation: Citation) => void;
}

// Luồng hội thoại: trạng thái trống có câu hỏi gợi ý theo vai trò, các lượt hỏi-đáp, tự cuộn xuống khi có nội dung mới.
export default function ChatThread({ assistant, onCite }: Props) {
  const user = useCurrentUser();
  const { state } = assistant;
  const endRef = useRef<HTMLDivElement>(null);
  const running = state.activeTurnId !== null;

  const lastText = state.turns.at(-1)?.text.length ?? 0;
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [state.turns.length, lastText]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4" aria-live="polite">
      {state.turns.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
          <span className="flex size-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
            <Sparkles className="size-6" aria-hidden="true" />
          </span>
          <p className="m-0 max-w-sm text-sm text-muted-foreground">
            Hỏi về quy chế, thủ tục và tình trạng hồ sơ thực tập, hoặc nhờ mở một trang (&quot;mở trang đề cương&quot;). Câu trả lời về quy định luôn kèm căn cứ; trợ lý chỉ cung cấp
            thông tin và không tự quyết định thay giảng viên hay nhà trường.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS[user.role].map((text) => (
              <button
                key={text}
                type="button"
                disabled={running}
                className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-foreground hover:border-primary/50 hover:bg-accent disabled:opacity-50"
                onClick={() => void assistant.ask(text)}
              >
                {text}
              </button>
            ))}
          </div>
        </div>
      ) : (
        state.turns.map((turn) => (
          <TurnView
            key={turn.turnId}
            turn={turn}
            onCite={onCite}
            onReload={() => void assistant.reload()}
            openedPages={turn.actions.flatMap((action) => {
              const page =
                action.type === "navigate" ? pageHref(user.role, action.page, { internshipId: action.internship_id, filters: action.filters }) : null;
              return page ? [page] : [];
            })}
          />
        ))
      )}
      <div ref={endRef} />
    </div>
  );
}
