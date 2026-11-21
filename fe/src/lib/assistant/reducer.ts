// Reducer trạng thái chat của trợ lý hỏi đáp, tổ chức theo turn_id.
// Thuần (không I/O): hook useAssistant phát action, thành phần chỉ đọc state.
import type {
  AssistantAction,
  Citation,
  ConversationDetail,
  ErrorCode,
  ServerFrame,
  Step,
  Verdict,
} from "@/lib/assistant-protocol";

// Mã lỗi hiển thị: mã của hợp đồng cộng các lỗi phát sinh ở phía FE.
export type UiErrorCode = ErrorCode | "ticket_failed" | "connection_failed" | "connection_lost" | "auth_failed";

export interface UiError {
  code: UiErrorCode;
  message: string;
}

export type TurnPhase = "running" | "done" | "error" | "cancelled" | "interrupted";

export interface TraceItem {
  kind: "status" | "tool_call" | "tool_result";
  text: string;
  step?: Step;
  name?: string;
  ok?: boolean;
}

export interface Turn {
  turnId: string;
  question: string;
  phase: TurnPhase;
  cancelling: boolean;
  trace: TraceItem[];
  step: Step | null;
  text: string; // phần đã stream, thay bằng answer khi có `final`
  citations: Citation[];
  verdict: Verdict | null;
  degraded: boolean;
  messageId: string | null;
  error: UiError | null;
  actions: AssistantAction[]; // hành động giao diện từ `final` của lượt đang chạy; lượt tải từ lịch sử luôn rỗng
}

export type ConnectionState = "idle" | "connecting" | "ready" | "reconnecting" | "closed";

export interface ChatState {
  conversationId: string | null;
  turns: Turn[];
  activeTurnId: string | null;
  connection: ConnectionState;
  notice: UiError | null; // lỗi không gắn với lượt nào (vd không mở được kết nối)
}

export type ChatAction =
  | { type: "ask"; turnId: string; question: string }
  | { type: "frame"; frame: ServerFrame }
  | { type: "cancel_requested"; turnId: string }
  | { type: "connection"; status: ConnectionState }
  | { type: "interrupt" } // mất kết nối giữa lượt: câu trả lời (nếu hoàn tất) sẽ nằm trong lịch sử BE
  | { type: "local_error"; error: UiError } // lỗi phát sinh ở FE: gắn vào lượt đang chạy, không có thì vào notice
  | { type: "conversation_loaded"; detail: ConversationDetail }
  | { type: "new_conversation" }
  | { type: "open_conversation"; id: string }
  | { type: "dismiss_notice" };

export const initialChatState: ChatState = {
  conversationId: null,
  turns: [],
  activeTurnId: null,
  connection: "idle",
  notice: null,
};

function newTurn(turnId: string, question: string): Turn {
  return {
    turnId,
    question,
    phase: "running",
    cancelling: false,
    trace: [],
    step: null,
    text: "",
    citations: [],
    verdict: null,
    degraded: false,
    messageId: null,
    error: null,
    actions: [],
  };
}

function updateTurn(state: ChatState, turnId: string, patch: (turn: Turn) => Turn): ChatState {
  if (!state.turns.some((turn) => turn.turnId === turnId)) return state;
  return { ...state, turns: state.turns.map((turn) => (turn.turnId === turnId ? patch(turn) : turn)) };
}

function finishActive(state: ChatState, turnId: string): string | null {
  return state.activeTurnId === turnId ? null : state.activeTurnId;
}

function applyFrame(state: ChatState, frame: ServerFrame): ChatState {
  if (frame.type === "ready" || frame.type === "pong") return state;

  // Khung không mang turn_id (chỉ có thể là lỗi chung) → gán cho lượt đang chạy.
  const turnId = frame.turn_id ?? state.activeTurnId;
  if (frame.type === "error" && !turnId) {
    return { ...state, notice: { code: frame.code, message: frame.message } };
  }
  if (!turnId) return state;

  // Khung của hội thoại khác (còn sót sau khi người dùng đổi hội thoại) thì bỏ.
  const conversationId = frame.conversation_id ?? null;
  if (conversationId && state.conversationId && conversationId !== state.conversationId) return state;

  const known = state.turns.some((turn) => turn.turnId === turnId);
  if (!known) return state;

  const adopted: ChatState =
    conversationId && !state.conversationId ? { ...state, conversationId } : state;

  // Lượt đã kết thúc (final/error/interrupt) thì bỏ khung tiến trình đến muộn.
  const current = state.turns.find((turn) => turn.turnId === turnId)!;
  if (current.phase !== "running" && frame.type !== "final" && frame.type !== "error") return state;

  switch (frame.type) {
    case "status":
      return updateTurn(adopted, turnId, (turn) => ({
        ...turn,
        step: frame.step,
        trace: [...turn.trace, { kind: "status", text: frame.text, step: frame.step }],
      }));
    case "tool_call":
      return updateTurn(adopted, turnId, (turn) => ({
        ...turn,
        trace: [...turn.trace, { kind: "tool_call", text: frame.label, name: frame.name }],
      }));
    case "tool_result":
      return updateTurn(adopted, turnId, (turn) => ({
        ...turn,
        trace: [...turn.trace, { kind: "tool_result", text: frame.summary, name: frame.name, ok: frame.ok }],
      }));
    case "token":
      return updateTurn(adopted, turnId, (turn) => ({ ...turn, text: turn.text + frame.delta }));
    case "final":
      return {
        ...updateTurn(adopted, turnId, (turn) => ({
          ...turn,
          phase: "done",
          cancelling: false,
          text: frame.answer,
          citations: frame.citations,
          verdict: frame.verdict,
          degraded: frame.degraded,
          messageId: frame.message_id,
          step: null,
          error: null,
          actions: frame.actions ?? [],
        })),
        activeTurnId: finishActive(adopted, turnId),
      };
    case "error":
      return {
        ...updateTurn(adopted, turnId, (turn) => ({
          ...turn,
          phase: frame.code === "cancelled" ? "cancelled" : "error",
          cancelling: false,
          step: null,
          error: { code: frame.code, message: frame.message },
        })),
        activeTurnId: finishActive(adopted, turnId),
      };
  }
}

// Dựng danh sách lượt từ tin nhắn đã lưu (gom theo turn_id, giữ thứ tự xuất hiện).
function turnsFromDetail(detail: ConversationDetail): Turn[] {
  const order: string[] = [];
  const byTurn = new Map<string, Turn>();
  for (const message of detail.messages) {
    let turn = byTurn.get(message.turn_id);
    if (!turn) {
      turn = { ...newTurn(message.turn_id, ""), phase: "interrupted" };
      byTurn.set(message.turn_id, turn);
      order.push(message.turn_id);
    }
    if (message.role === "user") {
      turn.question = message.content;
    } else {
      turn.phase = "done";
      turn.text = message.content;
      turn.citations = message.citations;
      turn.degraded = message.degraded;
      turn.messageId = message.id;
    }
  }
  return order.map((id) => byTurn.get(id)!);
}

function mergeLoaded(state: ChatState, detail: ConversationDetail): ChatState {
  if (state.conversationId && detail.id !== state.conversationId) return state;
  const fromServer = turnsFromDetail(detail);
  const local = new Map(state.turns.map((turn) => [turn.turnId, turn]));
  const merged: Turn[] = fromServer.map((turn) => {
    const old = local.get(turn.turnId);
    if (!old) return turn;
    // Máy chủ là nguồn đúng về nội dung; giữ lại phần chỉ có ở FE (vết, verdict).
    if (turn.phase === "done") return { ...turn, trace: old.trace, verdict: old.verdict };
    return { ...old, question: turn.question || old.question, phase: old.phase === "running" ? "interrupted" : old.phase };
  });
  const serverIds = new Set(fromServer.map((turn) => turn.turnId));
  for (const turn of state.turns) {
    if (!serverIds.has(turn.turnId)) {
      merged.push(turn.phase === "running" ? { ...turn, phase: "interrupted" } : turn);
    }
  }
  const active = merged.find((turn) => turn.phase === "running");
  return { ...state, conversationId: detail.id, turns: merged, activeTurnId: active?.turnId ?? null };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "ask":
      return {
        ...state,
        turns: [...state.turns, newTurn(action.turnId, action.question)],
        activeTurnId: action.turnId,
        notice: null,
      };
    case "frame":
      return applyFrame(state, action.frame);
    case "cancel_requested":
      return updateTurn(state, action.turnId, (turn) => (turn.phase === "running" ? { ...turn, cancelling: true } : turn));
    case "connection":
      return { ...state, connection: action.status };
    case "interrupt": {
      if (!state.activeTurnId) return state;
      return {
        ...updateTurn(state, state.activeTurnId, (turn) =>
          turn.phase === "running" ? { ...turn, phase: "interrupted", cancelling: false, step: null } : turn,
        ),
        activeTurnId: null,
      };
    }
    case "local_error": {
      const turnId = state.activeTurnId;
      if (!turnId) return { ...state, notice: action.error };
      return {
        ...updateTurn(state, turnId, (turn) => ({
          ...turn,
          phase: "error",
          cancelling: false,
          step: null,
          error: action.error,
        })),
        activeTurnId: null,
      };
    }
    case "conversation_loaded":
      return mergeLoaded(state, action.detail);
    case "new_conversation":
      return { ...initialChatState, connection: state.connection };
    case "open_conversation":
      return { ...initialChatState, conversationId: action.id, connection: state.connection };
    case "dismiss_notice":
      return { ...state, notice: null };
  }
}
