import { Plus } from "lucide-react";
import type { ConversationSummary } from "@/lib/assistant-protocol";
import { cn } from "@/lib/utils";

interface Props {
  conversations: ConversationSummary[];
  activeId: string | null;
  onNew: () => void;
  onOpen: (id: string) => void;
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}

// Cột danh sách hội thoại của trang /assistant toàn màn hình (ngăn bên dùng menu thả xuống thay vì cột này).
export default function ConversationList({ conversations, activeId, onNew, onOpen }: Props) {
  return (
    <nav className="flex flex-col gap-3 overflow-y-auto border-r border-border p-4" aria-label="Hội thoại">
      <button
        type="button"
        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-xs hover:bg-primary/90"
        onClick={onNew}
      >
        <Plus className="size-4" aria-hidden="true" />
        Hội thoại mới
      </button>
      {conversations.length === 0 ? (
        <p className="m-0 text-sm text-muted-foreground">Chưa có hội thoại nào.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                className={cn(
                  "flex w-full flex-col gap-0.5 rounded-lg border border-transparent px-2.5 py-2 text-left text-sm hover:bg-muted",
                  conversation.id === activeId && "border-border bg-muted",
                )}
                aria-current={conversation.id === activeId ? "true" : undefined}
                onClick={() => onOpen(conversation.id)}
              >
                <span className="truncate">{conversation.title || "Hội thoại chưa đặt tên"}</span>
                <small className="text-xs text-muted-foreground">{formatTime(conversation.updated_at)}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
