"use client";

import { ChevronsUpDown } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

export type SearchOption = { value: string; label: string };

// Ô chọn có tìm kiếm: gõ để lọc danh sách, bấm một mục để chọn. Giá trị chỉ lấy từ danh sách (không gõ tự do).
export default function SearchSelect({
  options,
  value,
  onChange,
  placeholder = "Chọn...",
  className,
}: {
  options: SearchOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selected = options.find((o) => o.value === value);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? options.filter((o) => o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q)) : options;
  }, [options, query]);

  return (
    <div className={cn("relative", className)}>
      <input
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        className="w-full pr-8"
        placeholder={placeholder}
        value={open ? query : (selected?.label ?? "")}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        onChange={(e) => setQuery(e.target.value)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "Escape" && open) {
            e.stopPropagation();
            setOpen(false);
          }
        }}
      />
      <ChevronsUpDown aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      {open && (
        <ul id={listId} role="listbox" onClick={(e) => e.preventDefault()} className="absolute z-10 mt-1 max-h-48 w-full list-none overflow-auto rounded-lg border-2 border-foreground/25 bg-popover p-1 shadow-lg">
          {filtered.length === 0 ? (
            <li className="px-2.5 py-2 text-sm text-muted-foreground">Không tìm thấy</li>
          ) : (
            filtered.map((o) => (
              <li
                key={o.value}
                role="option"
                aria-selected={o.value === value}
                // onMouseDown (không phải onClick) để chọn trước khi ô nhập mất focus và đóng danh sách.
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(o.value);
                  setOpen(false);
                }}
                className={cn("cursor-pointer rounded-md px-2.5 py-1.5 text-sm hover:bg-accent", o.value === value && "bg-accent font-medium")}
              >
                {o.label}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
