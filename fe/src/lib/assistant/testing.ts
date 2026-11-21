// Dữ liệu mẫu dùng chung cho test (không đưa vào bản build vì chỉ test import).
import type { Citation, ServerFrame } from "@/lib/assistant-protocol";

export const CITATION: Citation = {
  chunk_id: "QC-01:v1:d5:k2",
  doc_code: "QC-01",
  doc_title: "Quy chế thực tập (mẫu)",
  version: "v1",
  article: "Điều 5",
  clause: "2",
  effective_from: "2026-01-01",
  is_sample: true,
  quote: "Sinh viên nộp đề cương trong vòng 2 tuần kể từ ngày bắt đầu.",
};

export function frame<T extends ServerFrame["type"]>(
  type: T,
  fields: Omit<Extract<ServerFrame, { type: T }>, "type">,
): ServerFrame {
  return { type, ...fields } as ServerFrame;
}

export function turnFrame<T extends ServerFrame["type"]>(
  type: T,
  turnId: string,
  fields: Record<string, unknown> = {},
  conversationId = "c1",
): ServerFrame {
  return { type, turn_id: turnId, conversation_id: conversationId, ...fields } as unknown as ServerFrame;
}

export function finalFrame(turnId: string, overrides: Record<string, unknown> = {}, conversationId = "c1"): ServerFrame {
  return turnFrame(
    "final",
    turnId,
    {
      answer: "Nộp trong 2 tuần [cite:QC-01:v1:d5:k2].",
      citations: [CITATION],
      verdict: "answered",
      degraded: false,
      usage: {},
      trace_id: "tr1",
      message_id: "m2",
      ...overrides,
    },
    conversationId,
  );
}

// WebSocket giả: test tự mở, đẩy khung và ngắt kết nối.
export class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 0;
  sent: Record<string, unknown>[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  receive(frame: unknown) {
    this.onmessage?.({ data: JSON.stringify(frame) });
  }
  drop(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
  sentTypes() {
    return this.sent.map((frame) => frame.type);
  }
}

