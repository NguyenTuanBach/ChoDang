// Khung WebSocket giữa FE và BE (trợ lý hỏi đáp).
// Nguồn sự thật: .kiro/specs/agent-hoi-dap/contract.md — đổi ở đây phải đổi cả protocol.py của agent.

export type Step = "planning" | "searching" | "reading" | "answering" | "verifying";
export type ErrorCode =
  | "busy"
  | "rate_limited"
  | "timeout"
  | "cancelled"
  | "llm_unavailable"
  | "internal"
  | "invalid_frame";
export type Verdict = "answered" | "no_match" | "refused" | "needs_human" | "degraded" | "error_fallback";

export interface Citation {
  chunk_id: string;
  doc_code: string;
  doc_title: string;
  version: string;
  article: string;
  clause: string | null;
  effective_from: string;
  is_sample: boolean;
  quote: string;
}

// Hành động giao diện do trợ lý đề nghị (hiện chỉ có điều hướng). `page` là khóa trang (lib/nav.ts), FE tự đổi sang URL
// theo vai trò và bỏ qua khóa lạ. Chỉ có trong `final` của lượt đang chạy, không được lưu trong lịch sử hội thoại.
export interface AssistantAction {
  type: "navigate";
  page: string;
  label: string;
}

export interface Usage {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  provider?: string | null;
  model?: string | null;
}

// FE -> BE
export type ClientFrame =
  | { type: "auth"; ticket: string }
  | { type: "ask"; conversation_id: string | null; turn_id: string; question: string }
  | { type: "cancel"; turn_id: string }
  | { type: "ping" };

// BE -> FE (khung của lượt mang turn_id và conversation_id do BE thêm)
interface TurnScoped {
  turn_id: string;
  conversation_id: string;
}
export type ServerFrame =
  | { type: "ready" }
  | { type: "pong" }
  | ({ type: "status"; step: Step; text: string } & TurnScoped)
  | ({ type: "tool_call"; name: string; label: string } & TurnScoped)
  | ({ type: "tool_result"; name: string; ok: boolean; summary: string } & TurnScoped)
  | ({ type: "token"; delta: string } & TurnScoped)
  | ({
      type: "final";
      answer: string;
      citations: Citation[];
      verdict: Verdict;
      degraded: boolean;
      usage: Usage;
      trace_id: string;
      message_id: string;
      actions?: AssistantAction[];
    } & TurnScoped)
  | ({ type: "error"; code: ErrorCode; message: string } & Partial<TurnScoped>);

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  id: string;
  turn_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  degraded: boolean;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  messages: StoredMessage[];
}
