import type { Citation } from "@/lib/assistant-protocol";

// Nhãn ngắn trên chip, vd "Điều 5 khoản 2 · QC-01".
export function citationLabel(citation: Citation): string {
  const where = citation.clause ? `${citation.article} khoản ${citation.clause}` : citation.article;
  return `${where} · ${citation.doc_code}`;
}

// Lớp Tailwind của chip trích dẫn (xanh = quy chế, cam = văn bản mẫu, nét đứt = chưa xác minh).
export const CHIP_CLASS = "mx-0.5 inline-block rounded-full border border-primary bg-transparent px-2 text-xs leading-5 text-primary hover:bg-primary/10";
export const CHIP_SAMPLE_CLASS = "mx-0.5 inline-block rounded-full border border-warning bg-transparent px-2 text-xs leading-5 text-warning hover:bg-warning/10";
export const CHIP_UNKNOWN_CLASS = "mx-0.5 inline-block rounded-full border border-dashed border-muted-foreground px-2 text-xs leading-5 text-muted-foreground";
