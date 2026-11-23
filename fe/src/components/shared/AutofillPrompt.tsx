"use client";

import { Sparkles } from "lucide-react";
import FormDialog from "@/components/ui/dialog";
import { Button, Row } from "@/components/ui/ui";

// Hỏi ngay sau khi tải giấy lên: có muốn AI đọc giấy và tự điền không (chỉ gợi ý, người dùng vẫn xác nhận từng trường).
export default function AutofillPrompt({ open, onYes, onNo }: { open: boolean; onYes: () => void; onNo: () => void }) {
  return (
    <FormDialog
      title="Bạn có muốn AI tự điền không?"
      description="AI sẽ đọc giấy vừa tải (PDF, ảnh chụp hoặc bản scan) và gợi ý các trường. Bạn kiểm tra rồi xác nhận từng trường trước khi lưu."
      open={open}
      onOpenChange={(next) => {
        if (!next) onNo();
      }}
    >
      <Row>
        <Button variant="primary" onClick={onYes}>
          <Sparkles className="size-4" aria-hidden="true" /> Có, tự điền
        </Button>
        <Button onClick={onNo}>Để sau</Button>
      </Row>
    </FormDialog>
  );
}
