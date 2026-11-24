import { Download, FileText } from "lucide-react";

// Liên kết tải tệp qua endpoint kiểm quyền của BE (cùng origin, cookie phiên tự đính kèm). Hiện dạng thẻ tệp.
export default function DownloadDoc({ href, name }: { href: string; name: string }) {
  return (
    <a
      href={href}
      download
      className="inline-flex max-w-full items-center gap-2 rounded-lg border border-foreground/25 bg-background px-3 py-2 text-sm font-medium no-underline hover:bg-card"
    >
      <FileText aria-hidden className="size-4 shrink-0" />
      <span className="truncate">{name}</span>
      <Download aria-hidden className="size-4 shrink-0 text-muted-foreground" />
    </a>
  );
}
