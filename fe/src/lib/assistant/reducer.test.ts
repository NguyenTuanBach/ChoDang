import { describe, expect, it } from "vitest";
import type { ConversationDetail } from "@/lib/assistant-protocol";
import { chatReducer, initialChatState, type ChatAction, type ChatState } from "./reducer";
import { CITATION, finalFrame, turnFrame } from "./testing";

function run(actions: ChatAction[], from: ChatState = initialChatState): ChatState {
  return actions.reduce(chatReducer, from);
}
const ask = (turnId: string, question = "hỏi"): ChatAction => ({ type: "ask", turnId, question });
const frame = (f: ReturnType<typeof turnFrame>): ChatAction => ({ type: "frame", frame: f });

describe("chatReducer", () => {
  it("ask tạo lượt đang chạy", () => {
    const state = run([ask("t1", "Hạn nộp đề cương?")]);
    expect(state.activeTurnId).toBe("t1");
    expect(state.turns[0]).toMatchObject({ turnId: "t1", question: "Hạn nộp đề cương?", phase: "running", text: "" });
  });

  it("ghi vết status/tool_call/tool_result và nhận conversation_id từ BE", () => {
    const state = run([
      ask("t1"),
      frame(turnFrame("status", "t1", { step: "searching", text: "Đang tìm" })),
      frame(turnFrame("tool_call", "t1", { name: "search_policy", label: "Tra cứu quy chế" })),
      frame(turnFrame("tool_result", "t1", { name: "search_policy", ok: true, summary: "3 đoạn" })),
    ]);
    expect(state.conversationId).toBe("c1");
    expect(state.turns[0].step).toBe("searching");
    expect(state.turns[0].trace.map((item) => item.kind)).toEqual(["status", "tool_call", "tool_result"]);
    expect(state.turns[0].trace[2]).toMatchObject({ ok: true, text: "3 đoạn" });
  });

  it("nối token rồi final thay bằng answer, giữ citations/degraded/verdict", () => {
    const state = run([
      ask("t1"),
      frame(turnFrame("token", "t1", { delta: "Nộp " })),
      frame(turnFrame("token", "t1", { delta: "trong" })),
      { type: "frame", frame: finalFrame("t1", { degraded: true, verdict: "degraded" }) },
    ]);
    const turn = state.turns[0];
    expect(turn.phase).toBe("done");
    expect(turn.text).toContain("[cite:");
    expect(turn.citations).toEqual([CITATION]);
    expect(turn.degraded).toBe(true);
    expect(turn.verdict).toBe("degraded");
    expect(turn.messageId).toBe("m2");
    expect(state.activeTurnId).toBeNull();
  });

  it("khung của lượt khác không lẫn vào lượt đang chạy", () => {
    const state = run([
      ask("t1"),
      { type: "frame", frame: finalFrame("t1", { answer: "A", citations: [] }) },
      ask("t2"),
      frame(turnFrame("token", "t1", { delta: "muộn" })),
      frame(turnFrame("token", "t2", { delta: "mới" })),
      frame(turnFrame("token", "t-la", { delta: "lạ" })),
    ]);
    expect(state.turns[0].text).toBe("A");
    expect(state.turns[1].text).toBe("mới");
    expect(state.turns).toHaveLength(2);
  });

  it("bỏ khung của hội thoại khác", () => {
    const state = run([
      ask("t1"),
      frame(turnFrame("token", "t1", { delta: "a" })),
      frame(turnFrame("token", "t1", { delta: "b" }, "c-khac")),
    ]);
    expect(state.turns[0].text).toBe("a");
  });

  it("error gắn vào lượt; cancelled thành phase cancelled và giữ phần đã stream", () => {
    const state = run([
      ask("t1"),
      frame(turnFrame("token", "t1", { delta: "dở" })),
      { type: "cancel_requested", turnId: "t1" },
      frame(turnFrame("error", "t1", { code: "cancelled", message: "đã dừng" })),
    ]);
    expect(state.turns[0]).toMatchObject({ phase: "cancelled", text: "dở", cancelling: false });
    expect(state.activeTurnId).toBeNull();
  });

  it.each(["busy", "rate_limited", "timeout", "llm_unavailable"] as const)("lỗi %s đặt phase error", (code) => {
    const state = run([ask("t1"), frame(turnFrame("error", "t1", { code, message: "m" }))]);
    expect(state.turns[0]).toMatchObject({ phase: "error", error: { code, message: "m" } });
  });

  it("error không có turn_id gán cho lượt đang chạy; không có lượt thì vào notice", () => {
    const withTurn = run([ask("t1"), { type: "frame", frame: { type: "error", code: "rate_limited", message: "chậm" } }]);
    expect(withTurn.turns[0].error?.code).toBe("rate_limited");
    const without = run([{ type: "frame", frame: { type: "error", code: "invalid_frame", message: "x" } }]);
    expect(without.notice?.code).toBe("invalid_frame");
  });

  it("interrupt đánh dấu lượt đang chạy là interrupted", () => {
    const state = run([ask("t1"), { type: "interrupt" }]);
    expect(state.turns[0].phase).toBe("interrupted");
    expect(state.activeTurnId).toBeNull();
  });

  it("local_error gắn vào lượt đang chạy, không có thì notice", () => {
    const a = run([ask("t1"), { type: "local_error", error: { code: "ticket_failed", message: "x" } }]);
    expect(a.turns[0]).toMatchObject({ phase: "error", error: { code: "ticket_failed" } });
    const b = run([{ type: "local_error", error: { code: "connection_failed", message: "y" } }]);
    expect(b.notice?.code).toBe("connection_failed");
  });

  describe("conversation_loaded", () => {
    const detail: ConversationDetail = {
      id: "c1",
      title: "T",
      messages: [
        { id: "m1", turn_id: "t1", role: "user", content: "Câu 1", citations: [], degraded: false, created_at: "" },
        { id: "m2", turn_id: "t1", role: "assistant", content: "Đáp 1", citations: [CITATION], degraded: true, created_at: "" },
        { id: "m3", turn_id: "t2", role: "user", content: "Câu 2", citations: [], degraded: false, created_at: "" },
      ],
    };

    it("mở hội thoại cũ dựng lượt từ tin nhắn; lượt thiếu đáp án là interrupted", () => {
      const state = run([{ type: "open_conversation", id: "c1" }, { type: "conversation_loaded", detail }]);
      expect(state.turns.map((t) => [t.turnId, t.question, t.phase])).toEqual([
        ["t1", "Câu 1", "done"],
        ["t2", "Câu 2", "interrupted"],
      ]);
      expect(state.turns[0]).toMatchObject({ text: "Đáp 1", degraded: true, messageId: "m2" });
      expect(state.activeTurnId).toBeNull();
    });

    it("sau khi nối lại: lượt đang chạy đã có đáp án ở BE thì thành done, giữ vết ở FE", () => {
      const before = run([
        ask("t1", "Câu 1"),
        frame(turnFrame("tool_call", "t1", { name: "n", label: "L" })),
        { type: "interrupt" },
      ]);
      const state = run([{ type: "conversation_loaded", detail }], before);
      expect(state.turns[0]).toMatchObject({ phase: "done", text: "Đáp 1" });
      expect(state.turns[0].trace).toHaveLength(1);
    });

    it("lượt chỉ có ở FE được giữ lại (đánh dấu interrupted nếu đang chạy)", () => {
      const before = run([ask("t9", "Chưa tới BE"), frame(turnFrame("token", "t9", { delta: "x" }))]);
      const state = run([{ type: "conversation_loaded", detail }], before);
      expect(state.turns.at(-1)).toMatchObject({ turnId: "t9", phase: "interrupted" });
    });

    it("bỏ qua hội thoại khác với hội thoại đang mở", () => {
      const before = run([{ type: "open_conversation", id: "c-khac" }]);
      expect(run([{ type: "conversation_loaded", detail }], before).turns).toEqual([]);
    });
  });

  it("new_conversation xóa lượt nhưng giữ trạng thái kết nối", () => {
    const state = run([{ type: "connection", status: "ready" }, ask("t1"), { type: "new_conversation" }]);
    expect(state).toMatchObject({ turns: [], conversationId: null, connection: "ready" });
  });
});
