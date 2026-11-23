"use client";

import { FileText, Loader2, X } from "lucide-react";
import Link from "next/link";
import { FIELD_LABEL, KIND_LABEL } from "@/lib/autofill";
import { cn } from "@/lib/utils";
import { useAssistantContext, type AutofillCardItem } from "./AssistantProvider";

// Thẻ gợi ý sau khi đính kèm giấy trong Trợ lý: loại giấy + các trường AI đọc được. Trang đích đã được mở và điền nháp (chưa lưu).
function Card({ card, onDismiss }: { card: AutofillCardItem; onDismiss: () => void }) {
  const fields = Object.entries(card.result?.fields ?? {});
  return (
    <div className={cn("relative rounded-lg border-2 bg-background p-3 text-sm", card.status === "error" ? "border-destructive/40" : "border-beige-strong")}>
      <button type="button" className="absolute right-2 top-2 rounded p-0.5 text-muted-foreground hover:bg-muted" aria-label="Ẩn thẻ" onClick={onDismiss}>
        <X className="size-3.5" />
      </button>
      <p className="m-0 flex items-center gap-1.5 pr-6 font-medium">
        {card.status === "reading" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <FileText className="size-4" aria-hidden="true" />}
        <span className="truncate">{card.filename}</span>
      </p>
      {card.status === "reading" && <p className="m-0 mt-1 text-muted-foreground">AI đang đọc giấy...</p>}
      {card.status === "error" && <p className="m-0 mt-1 text-destructive">{card.error}</p>}
      {card.status === "done" && card.result && (
        <>
          <p className="m-0 mt-1 text-muted-foreground">
            {KIND_LABEL[card.result.kind]} · AI đọc được {fields.length} trường. Đã điền nháp ở trang bên cạnh, bạn kiểm tra rồi bấm nút đang nhấp nháy để lưu.
          </p>
          <ul className="m-0 mt-2 max-h-40 list-none space-y-0.5 overflow-y-auto p-0">
            {fields.map(([key, s]) => (
              <li key={key} className="flex gap-1.5">
                <span className="shrink-0 text-muted-foreground">{FIELD_LABEL[key] ?? key}:</span>
                <span className="truncate font-medium" title={s.value}>
                  {s.value}
                </span>
                {s.confidence < 0.8 && <span className="shrink-0 text-xs text-amber-700">(cần kiểm)</span>}
              </li>
            ))}
          </ul>
          {(card.result.warnings ?? []).map((w) => (
            <p key={w} className="m-0 mt-1 text-destructive">
              {w}
            </p>
          ))}
          {card.href && (
            <Link href={card.href} className="mt-2 inline-block text-primary underline">
              Mở trang để xác nhận
            </Link>
          )}
        </>
      )}
    </div>
  );
}

export default function AutofillCards() {
  const { autofillCards, dismissAutofillCard } = useAssistantContext();
  if (autofillCards.length === 0) return null;
  return (
    <div className="mx-3 mb-2 max-h-[45%] space-y-2 overflow-y-auto" aria-label="Giấy đã đính kèm">
      {autofillCards.map((card) => (
        <Card key={card.id} card={card} onDismiss={() => dismissAutofillCard(card.id)} />
      ))}
    </div>
  );
}
