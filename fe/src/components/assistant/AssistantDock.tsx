"use client";

import { Sparkles } from "lucide-react";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";
import { useAssistantContext } from "./AssistantProvider";
import AssistantPanel from "./AssistantPanel";

const FULL_PAGE = "/assistant";

// Ngăn Trợ lý bên phải: máy tính (>= 1024px) là cột cố định đẩy nội dung; màn hình nhỏ là ngăn trượt (Sheet).
// Đóng thì có nút nổi góc dưới phải. Không hiện trên /assistant (đã là chat toàn màn hình). Nằm ở layout nên chuyển trang không dựng lại.
function Dock({ pathname }: { pathname: string }) {
  const { open, setOpen } = useAssistantContext();
  const wide = useMediaQuery("(min-width: 1024px)");
  if (pathname === FULL_PAGE) return null;

  return (
    <>
      {wide ? (
        <aside
          aria-label="Ngăn Trợ lý"
          aria-hidden={!open}
          inert={!open}
          className={cn("sticky top-0 h-svh shrink-0 overflow-hidden transition-[width] duration-200 ease-linear", open ? "w-[26rem]" : "w-0")}
        >
          <div className="h-full w-[26rem] py-2 pr-2">
            <div className="h-full overflow-hidden rounded-xl border-2 border-foreground/25 bg-card shadow-sm">
              <AssistantPanel onClose={() => setOpen(false)} />
            </div>
          </div>
        </aside>
      ) : (
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md" showCloseButton={false}>
            <SheetTitle className="sr-only">Trợ lý thực tập</SheetTitle>
            <SheetDescription className="sr-only">Hỏi đáp về quy chế, thủ tục và hồ sơ thực tập</SheetDescription>
            <AssistantPanel onClose={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      )}

      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground shadow-lg transition-transform hover:scale-105 hover:bg-primary/90"
          aria-label="Mở Trợ lý (Ctrl+J)"
          title="Hỏi Trợ lý (Ctrl+J)"
        >
          <Sparkles className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline">Hỏi Trợ lý</span>
        </button>
      )}
    </>
  );
}

function CurrentDock() {
  return <Dock pathname={usePathname()} />;
}

export default function AssistantDock() {
  return (
    <Suspense fallback={null}>
      <CurrentDock />
    </Suspense>
  );
}

// Nút bật/tắt ngăn Trợ lý trên thanh trên (ẩn ở /assistant).
function Toggle({ pathname }: { pathname: string }) {
  const { open, toggle } = useAssistantContext();
  if (pathname === FULL_PAGE) return null;
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={open}
      aria-label="Bật/tắt Trợ lý (Ctrl+J)"
      title="Trợ lý (Ctrl+J)"
      className={cn(
        "inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition-colors hover:bg-muted",
        open ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Sparkles className="size-4" aria-hidden="true" />
      <span className="hidden sm:inline">Trợ lý</span>
    </button>
  );
}

function CurrentToggle() {
  return <Toggle pathname={usePathname()} />;
}

export function AssistantToggle() {
  return (
    <Suspense fallback={null}>
      <CurrentToggle />
    </Suspense>
  );
}
