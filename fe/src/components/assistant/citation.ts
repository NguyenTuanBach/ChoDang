import type { Citation } from "@/lib/assistant-protocol";

// Nhãn ngắn trên chip, vd "Điều 5 khoản 2 · QC-01".
export function citationLabel(citation: Citation): string {
  const where = citation.clause ? `${citation.article} khoản ${citation.clause}` : citation.article;
  return `${where} · ${citation.doc_code}`;
}
