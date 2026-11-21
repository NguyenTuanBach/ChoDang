import { ArrowLeft } from "lucide-react";
import type { Citation } from "@/lib/assistant-protocol";
import { SAMPLE_WARNING } from "./messages";
import { citationLabel } from "./citation";

interface Props {
  citation: Citation;
  onClose: () => void;
}

// Xem nguyên văn điều/khoản được trích. `quote` hiển thị dạng văn bản thuần.
export default function CitationPanel({ citation, onClose }: Props) {
  return (
    <aside className="flex h-full flex-col gap-3 overflow-y-auto p-4" aria-label="Nguyên văn trích dẫn">
      <div className="flex items-center justify-between gap-2">
        <strong className="text-sm">{citationLabel(citation)}</strong>
        <button type="button" className="inline-flex items-center gap-1 text-sm text-primary hover:underline" onClick={onClose} aria-label="Đóng nguyên văn">
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Đóng
        </button>
      </div>
      <p className="m-0 text-xs text-muted-foreground">
        {citation.doc_title} · phiên bản {citation.version} · hiệu lực từ {citation.effective_from}
      </p>
      {citation.is_sample && (
        <p className="m-0 rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-sm text-warning" role="note">
          {SAMPLE_WARNING}
        </p>
      )}
      <blockquote className="m-0 whitespace-pre-wrap rounded-lg border-l-4 border-primary bg-muted px-3 py-2 text-sm leading-relaxed">{citation.quote}</blockquote>
    </aside>
  );
}
