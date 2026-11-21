import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ConversationDetail } from "@/lib/assistant-protocol";
import { CITATION, FakeSocket, finalFrame, turnFrame } from "./testing";
import { useAssistant } from "./useAssistant";

const detail: ConversationDetail = {
  id: "c1",
  title: "Hạn nộp",
  messages: [
    { id: "m1", turn_id: "t1", role: "user", content: "Hạn nộp?", citations: [], degraded: false, created_at: "" },
    { id: "m2", turn_id: "t1", role: "assistant", content: "Trong 2 tuần.", citations: [CITATION], degraded: false, created_at: "" },
  ],
};

let ticketCount = 0;
let conversationDetail: ConversationDetail | Response = detail;
let ticketResponse: () => Response;

const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input);
  if (url === "/api/assistant/ws-ticket" && init?.method === "POST") {
    ticketCount += 1;
    return ticketResponse();
  }
  if (url === "/api/assistant/conversations") {
    return new Response(JSON.stringify([{ id: "c1", title: "Hạn nộp", created_at: "", updated_at: "" }]));
  }
  if (url === "/api/assistant/conversations/c1") {
    return conversationDetail instanceof Response ? conversationDetail : new Response(JSON.stringify(conversationDetail));
  }
  return new Response("{}", { status: 404 });
}) as unknown as typeof fetch;

function setup(extra = {}) {
  return renderHook(() =>
    useAssistant({
      wsUrl: "ws://test/api/assistant/ws",
      createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
      fetchImpl,
      newTurnId: () => "t1",
      backoffMs: [5, 5],
      pollMs: 5,
      pollAttempts: 3,
      pingMs: 0,
      handshakeMs: 500,
      ...extra,
    }),
  );
}

// Đi qua bắt tay: chờ socket xuất hiện, mở, gửi `ready`.
async function handshake(index = 0): Promise<FakeSocket> {
  await waitFor(() => expect(FakeSocket.instances[index]).toBeDefined());
  const socket = FakeSocket.instances[index];
  act(() => socket.open());
  await waitFor(() => expect(socket.sentTypes()).toContain("auth"));
  act(() => socket.receive({ type: "ready" }));
  return socket;
}

beforeEach(() => {
  FakeSocket.instances = [];
  ticketCount = 0;
  conversationDetail = detail;
  ticketResponse = () => new Response(JSON.stringify({ ticket: `tk${ticketCount}`, expires_in: 30 }));
  vi.mocked(fetchImpl).mockClear();
});
afterEach(() => vi.restoreAllMocks());

describe("useAssistant", () => {
  it("ticket → auth → ask → khung tiến trình/token/final", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.conversations).toHaveLength(1));

    let pending!: Promise<void>;
    act(() => {
      pending = result.current.ask("  Hạn nộp?  ");
    });
    const socket = await handshake();
    await act(() => pending);

    expect(socket.sent[0]).toEqual({ type: "auth", ticket: "tk1" });
    expect(socket.sent[1]).toEqual({ type: "ask", conversation_id: null, turn_id: "t1", question: "Hạn nộp?" });
    expect(socket.url).toBe("ws://test/api/assistant/ws");
    expect(result.current.state.connection).toBe("ready");

    act(() => {
      socket.receive(turnFrame("status", "t1", { step: "searching", text: "Đang tìm" }));
      socket.receive(turnFrame("token", "t1", { delta: "Trong " }));
    });
    expect(result.current.state.conversationId).toBe("c1");
    expect(result.current.state.turns[0]).toMatchObject({ step: "searching", text: "Trong " });

    act(() => socket.receive(finalFrame("t1")));
    expect(result.current.state.turns[0]).toMatchObject({ phase: "done", citations: [CITATION] });
    expect(result.current.state.activeTurnId).toBeNull();
  });

  it("lượt sau dùng lại kết nối và gửi conversation_id", async () => {
    let n = 0;
    const { result } = setup({ newTurnId: () => `t${(n += 1)}` });
    act(() => void result.current.ask("một"));
    const socket = await handshake();
    await waitFor(() => expect(socket.sentTypes()).toContain("ask"));
    act(() => socket.receive(finalFrame("t1")));

    await act(() => result.current.ask("hai"));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(ticketCount).toBe(1);
    expect(socket.sent.at(-1)).toEqual({ type: "ask", conversation_id: "c1", turn_id: "t2", question: "hai" });
  });

  it("không gửi khi câu hỏi rỗng hoặc đang có lượt chạy", async () => {
    const { result } = setup();
    await act(() => result.current.ask("   "));
    expect(result.current.state.turns).toHaveLength(0);
    act(() => void result.current.ask("a"));
    await act(() => result.current.ask("b"));
    expect(result.current.state.turns).toHaveLength(1);
    await handshake();
  });

  it("cancel gửi khung cancel với turn_id đang chạy", async () => {
    const { result } = setup();
    act(() => void result.current.ask("hỏi"));
    const socket = await handshake();
    await waitFor(() => expect(socket.sentTypes()).toContain("ask"));

    act(() => result.current.cancel());
    expect(socket.sent.at(-1)).toEqual({ type: "cancel", turn_id: "t1" });
    expect(result.current.state.turns[0].cancelling).toBe(true);

    act(() => socket.receive(turnFrame("error", "t1", { code: "cancelled", message: "Đã dừng" })));
    expect(result.current.state.turns[0].phase).toBe("cancelled");
  });

  it("lỗi cấp vé → lượt báo lỗi ticket_failed, không mở WebSocket", async () => {
    ticketResponse = () => new Response(JSON.stringify({ error: { code: "x", message: "Chưa đăng nhập" } }), { status: 401 });
    const { result } = setup();
    await act(() => result.current.ask("hỏi"));
    expect(result.current.state.turns[0]).toMatchObject({ phase: "error", error: { code: "ticket_failed", message: "Chưa đăng nhập" } });
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("đóng 4401 khi bắt tay → auth_failed", async () => {
    const { result } = setup();
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.ask("hỏi");
    });
    await waitFor(() => expect(FakeSocket.instances[0]).toBeDefined());
    act(() => FakeSocket.instances[0].drop(4401));
    await act(() => pending);
    expect(result.current.state.turns[0].error?.code).toBe("auth_failed");
    expect(result.current.state.connection).toBe("closed");
  });

  it("mất kết nối giữa lượt: nối lại bằng vé mới rồi tải lại hội thoại", async () => {
    const { result } = setup();
    act(() => void result.current.ask("Hạn nộp?"));
    const first = await handshake();
    await waitFor(() => expect(first.sentTypes()).toContain("ask"));
    act(() => first.receive(turnFrame("token", "t1", { delta: "Trong" })));

    act(() => first.drop());
    expect(result.current.state.turns[0].phase).toBe("interrupted");
    expect(result.current.state.connection).toBe("reconnecting");

    const second = await handshake(1);
    expect(second.sent[0]).toEqual({ type: "auth", ticket: "tk2" });
    await waitFor(() => expect(result.current.state.turns[0]).toMatchObject({ phase: "done", text: "Trong 2 tuần." }));
    expect(result.current.state.connection).toBe("ready");
    expect(fetchImpl).toHaveBeenCalledWith("/api/assistant/conversations/c1", expect.anything());
  });

  it("nối lại xong mà BE chưa có câu trả lời thì hỏi lại định kỳ cho tới khi có", async () => {
    const pendingDetail: ConversationDetail = { ...detail, messages: [detail.messages[0]] };
    conversationDetail = pendingDetail;
    const { result } = setup();
    act(() => void result.current.ask("Hạn nộp?"));
    const first = await handshake();
    await waitFor(() => expect(first.sentTypes()).toContain("ask"));
    act(() => first.receive(turnFrame("token", "t1", { delta: "x" })));
    act(() => first.drop());
    await handshake(1);
    await waitFor(() => expect(result.current.state.turns[0].phase).toBe("interrupted"));

    conversationDetail = detail;
    await waitFor(() => expect(result.current.state.turns[0].phase).toBe("done"));
  });

  it("hết lượt nối lại thì báo connection_failed", async () => {
    const { result } = setup({ backoffMs: [2, 2] });
    act(() => void result.current.ask("hỏi"));
    const first = await handshake();
    await waitFor(() => expect(first.sentTypes()).toContain("ask"));
    act(() => first.receive(turnFrame("token", "t1", { delta: "x" })));
    act(() => first.drop());

    for (const index of [1, 2]) {
      await waitFor(() => expect(FakeSocket.instances[index]).toBeDefined());
      act(() => FakeSocket.instances[index].drop(1006));
    }
    await waitFor(() => expect(result.current.state.notice?.code).toBe("connection_failed"));
    expect(result.current.state.connection).toBe("closed");
  });

  it("mất kết nối khi chưa biết hội thoại → lỗi connection_lost, không nối lại", async () => {
    const { result } = setup();
    act(() => void result.current.ask("hỏi"));
    const first = await handshake();
    await waitFor(() => expect(first.sentTypes()).toContain("ask"));
    act(() => first.drop());
    expect(result.current.state.turns[0].error?.code).toBe("connection_lost");
  });

  it("đóng yên lặng khi không có lượt: không nối lại; lượt sau mở kết nối mới", async () => {
    const { result } = setup();
    act(() => void result.current.ask("một"));
    const first = await handshake();
    await waitFor(() => expect(first.sentTypes()).toContain("ask"));
    act(() => first.receive(finalFrame("t1")));
    act(() => first.drop(4408));
    expect(result.current.state.connection).toBe("closed");
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("openConversation tải lịch sử; newConversation xóa", async () => {
    const { result } = setup();
    await act(() => result.current.openConversation("c1"));
    expect(result.current.state.conversationId).toBe("c1");
    expect(result.current.state.turns[0]).toMatchObject({ question: "Hạn nộp?", phase: "done" });
    act(() => result.current.newConversation());
    expect(result.current.state.turns).toEqual([]);
    expect(result.current.state.conversationId).toBeNull();
  });

  it("đóng socket khi gỡ hook", async () => {
    const { result, unmount } = setup();
    act(() => void result.current.ask("hỏi"));
    const socket = await handshake();
    await waitFor(() => expect(socket.sentTypes()).toContain("ask"));
    unmount();
    expect(socket.readyState).toBe(3);
    expect(FakeSocket.instances).toHaveLength(1);
  });
});
