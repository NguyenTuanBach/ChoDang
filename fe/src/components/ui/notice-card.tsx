import { AlertTriangle, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "info" | "warning" | "error";

const TONE: Record<Tone, { bar: string; icon: string; Icon: typeof Info }> = {
  info: { bar: "border-l-foreground/40", icon: "text-muted-foreground", Icon: Info },
  warning: { bar: "border-l-amber-500", icon: "text-amber-600", Icon: AlertTriangle },
  error: { bar: "border-l-red-600", icon: "text-red-600", Icon: XCircle },
};

// Thẻ thông báo gọn: nền trắng, viền đen nhạt như các thẻ khác, chỉ nhấn bằng vạch màu bên trái và biểu tượng (không tô cả thẻ).
export default function NoticeCard({ tone = "info", title, children, className }: { tone?: Tone; title: string; children: ReactNode; className?: string }) {
  const { bar, icon, Icon } = TONE[tone];
  return (
    <div role={tone === "info" ? undefined : "alert"} className={cn("rounded-lg border-2 border-l-4 border-foreground/25 bg-background px-3 py-2.5 text-sm", bar, className)}>
      <p className="m-0 flex items-center gap-1.5 font-semibold">
        <Icon aria-hidden className={cn("size-4 shrink-0", icon)} />
        {title}
      </p>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}
