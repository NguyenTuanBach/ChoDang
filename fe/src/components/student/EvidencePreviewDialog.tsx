"use client";

import { FileText } from "lucide-react";
import { useEffect, useMemo } from "react";
import FormDialog from "@/components/ui/dialog";
import { Button, Row } from "@/components/ui/ui";

function sizeText(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Popup xem lại tệp vừa chọn trước khi tải minh chứng lên: ảnh và PDF xem được ngay, loại khác chỉ hiện thông tin tệp.
export default function EvidencePreviewDialog({
  file,
  busy,
  onConfirm,
  onCancel,
  title = "Xem lại minh chứng",
}: {
  file: File | null;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
}) {
  // Địa chỉ tạm của tệp để xem trước; thu hồi khi đổi tệp hoặc đóng popup.
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  const isImage = file?.type.startsWith("image/") ?? false;
  const isPdf = file?.type === "application/pdf";

  return (
    <FormDialog title={title} wide open={file !== null} onOpenChange={(open) => !open && !busy && onCancel()}>
      {file && (
        <>
          <div className="mb-3 flex items-center gap-2 text-sm">
            <FileText aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 truncate font-medium">{file.name}</span>
            <span className="shrink-0 text-muted-foreground">{sizeText(file.size)}</span>
            {url && (isImage || isPdf) && (
              <a href={url} target="_blank" rel="noreferrer" className="ml-auto shrink-0 text-sm font-medium text-foreground underline underline-offset-2">
                Mở tab mới
              </a>
            )}
          </div>
          <div className="mb-4 flex max-h-[72vh] min-h-64 items-center justify-center overflow-auto rounded-lg border-2 border-foreground/25 bg-background">
            {url && isImage && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={url} alt={file.name} className="max-h-[72vh] w-auto max-w-full object-contain" />
            )}
            {url && isPdf && <iframe src={url} title={file.name} className="h-[72vh] w-full" />}
            {!isImage && !isPdf && <p className="m-4 text-sm text-muted-foreground">Không xem trước được loại tệp này. Kiểm tra lại tên tệp rồi tải lên.</p>}
          </div>
          <Row>
            <Button variant="primary" disabled={busy} onClick={onConfirm}>
              {busy ? "Đang tải lên..." : "Tải lên"}
            </Button>
            <Button disabled={busy} onClick={onCancel}>
              Hủy
            </Button>
          </Row>
        </>
      )}
    </FormDialog>
  );
}
