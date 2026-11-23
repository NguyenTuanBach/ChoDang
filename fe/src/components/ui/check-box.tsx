"use client";

import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

// Ô tích tròn trịa: chưa tích là khung rỗng, tích rồi thì xanh lá kèm dấu tích. Bấm cả dòng (nhãn) để đổi.
export default function CheckBox({
  checked,
  onChange,
  children,
  disabled,
  className,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children?: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn("group flex w-full items-center gap-3 rounded-lg text-left text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60", className)}
    >
      <span
        className={cn(
          "flex size-5 shrink-0 items-center justify-center rounded-md border-2 transition-colors",
          checked ? "border-green-600 bg-green-600 text-white" : "border-foreground/30 bg-background group-hover:border-foreground/60",
        )}
      >
        <Check aria-hidden className={cn("size-3.5 transition-opacity", checked ? "opacity-100" : "opacity-0")} strokeWidth={3} />
      </span>
      <span className={cn("min-w-0 flex-1 break-words transition-colors", checked && "text-muted-foreground")}>{children}</span>
    </button>
  );
}
