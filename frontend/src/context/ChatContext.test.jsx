import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "../lib/api";
import { ChatProvider, useChat } from "./ChatContext";

vi.mock("../lib/api", () => ({ streamChat: vi.fn() }));

const setup = () => renderHook(() => useChat(), { wrapper: ChatProvider });

/** Giả lập máy chủ: gọi lần lượt các sự kiện SSE. */
const emits = (...events) => streamChat.mockImplementation(async (_q, _id, onEvent) => { events.forEach(onEvent); });

beforeEach(() => {
  streamChat.mockReset();
});

describe("ChatContext", () => {
  it("bắt đầu rỗng và không bận", () => {
    const { result } = setup();
    expect(result.current.messages).toEqual([]);
    expect(result.current.busy).toBe(false);
  });

  it("hỏi: thêm câu hỏi và một câu trả lời chờ, bận cho tới khi xong", async () => {
    let finish;
    streamChat.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const { result } = setup();
    let pending;
    act(() => { pending = result.current.ask("Tối thiểu mấy tuần?"); });
    expect(result.current.busy).toBe(true);
    expect(result.current.messages).toEqual([
      { role: "user", content: "Tối thiểu mấy tuần?" },
      { role: "assistant", content: "", status: "Đang gửi câu hỏi…" },
    ]);
    await act(async () => { finish(); await pending; });
    expect(result.current.busy).toBe(false);
  });

  it("sự kiện stage cập nhật trạng thái; delta nối thêm chữ và xóa trạng thái", async () => {
    emits({ type: "stage", label: "Tìm quy định" });
    const { result } = setup();
    await act(() => result.current.ask("q"));
    expect(result.current.messages[1].status).toBe("Tìm quy định…");

    emits({ type: "delta", text: "Tối thiểu " }, { type: "delta", text: "8 tuần" });
    await act(() => result.current.ask("q2"));
    expect(result.current.messages[3]).toMatchObject({ content: "Tối thiểu 8 tuần", status: "" });
  });

  it("sự kiện done thay bằng câu trả lời đã kiểm chứng kèm nguồn, chế độ và gợi ý gia hạn", async () => {
    emits(
      { type: "delta", text: "nháp" },
      { type: "done", answer: "Tối thiểu 8 tuần [1].", citations: [{ n: 1, label: "Điều 3" }], suggest_extension: true, mode: "extractive_timeout", conversation_id: 7 },
    );
    const { result } = setup();
    await act(() => result.current.ask("q"));
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant", content: "Tối thiểu 8 tuần [1].", citations: [{ n: 1, label: "Điều 3" }], suggest: true, mode: "extractive_timeout", status: "",
    });
  });

  it("giữ conversation_id từ lần trả lời trước để các câu sau cùng một hội thoại", async () => {
    emits({ type: "done", answer: "a", citations: [], conversation_id: 42 });
    const { result } = setup();
    await act(() => result.current.ask("câu 1"));
    expect(streamChat.mock.calls[0][1]).toBeNull();
    await act(() => result.current.ask("câu 2"));
    expect(streamChat.mock.calls[1][1]).toBe(42);
    expect(result.current.messages).toHaveLength(4);
  });

  it("sự kiện error hiện nội dung lỗi trong câu trả lời và mở lại ô nhập", async () => {
    emits({ type: "error", detail: "Nhà cung cấp mô hình đang lỗi" });
    const { result } = setup();
    await act(() => result.current.ask("q"));
    expect(result.current.messages[1]).toMatchObject({ content: "Nhà cung cấp mô hình đang lỗi", status: "" });
    expect(result.current.busy).toBe(false);
  });

  it("lỗi mạng/HTTP trước khi mở stream cũng hiện trong khung chat, không ném ra ngoài", async () => {
    streamChat.mockRejectedValue(new Error("Quá nhiều yêu cầu, thử lại sau"));
    const { result } = setup();
    await act(() => result.current.ask("q"));
    expect(result.current.messages[1].content).toBe("Quá nhiều yêu cầu, thử lại sau");
    expect(result.current.busy).toBe(false);
  });
});
