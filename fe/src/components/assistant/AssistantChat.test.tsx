import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CITATION, FakeSocket, finalFrame, turnFrame } from "@/lib/assistant/testing";
import { UserContext } from "@/lib/user-context";
import AssistantChat from "./AssistantChat";
import AssistantProvider from "./AssistantProvider";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/assistant" }));

const USER = { id: "3", email: "sv.a@example.test", full_name: "Sinh viên A (mẫu)", role: "student" } as const;

const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input);
  if (url === "/api/assistant/ws-ticket" && init?.method === "POST") {
    return new Response(JSON.stringify({ ticket: "tk", expires_in: 30 }));
  }
  if (url === "/api/assistant/conversations") {
    return new Response(
      JSON.stringify([{ id: "c1", title: "Hạn nộp đề cương", created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" }]),
    );
  }
  if (url === "/api/assistant/conversations/c1") {
    return new Response(
      JSON.stringify({
        id: "c1",
        title: "Hạn nộp đề cương",
        messages: [
          { id: "m1", turn_id: "old", role: "user", content: "Câu hỏi cũ", citations: [], degraded: false, created_at: "" },
          { id: "m2", turn_id: "old", role: "assistant", content: "Đáp cũ [cite:QC-01:v1:d5:k2]", citations: [CITATION], degraded: true, created_at: "" },
        ],
      }),
    );
  }
  return new Response("{}", { status: 404 });
}) as unknown as typeof fetch;

function renderChat() {
  return render(
    <UserContext.Provider value={USER}>
      <AssistantProvider
        options={{
          wsUrl: "ws://test/ws",
          createSocket: (url: string) => new FakeSocket(url) as unknown as WebSocket,
          fetchImpl,
          newTurnId: () => "t1",
          pingMs: 0,
          backoffMs: [],
        }}
      >
        <AssistantChat />
      </AssistantProvider>
    </UserContext.Provider>,
  );
}

async function sendQuestion(user: ReturnType<typeof userEvent.setup>, text: string): Promise<FakeSocket> {
  await user.type(screen.getByLabelText("Câu hỏi"), text);
  await user.click(screen.getByRole("button", { name: "Gửi" }));
  await waitFor(() => expect(FakeSocket.instances[0]).toBeDefined());
  const socket = FakeSocket.instances[0];
  act(() => socket.open());
  await waitFor(() => expect(socket.sentTypes()).toContain("auth"));
  act(() => socket.receive({ type: "ready" }));
  await waitFor(() => expect(socket.sentTypes()).toContain("ask"));
  return socket;
}

beforeEach(() => {
  FakeSocket.instances = [];
});

describe("AssistantChat", () => {
  it("hiển thị tiến trình, stream token, rồi câu trả lời với chip trích dẫn mở panel nguyên văn", async () => {
    const user = userEvent.setup();
    renderChat();
    const socket = await sendQuestion(user, "Hạn nộp đề cương?");

    expect(screen.getByText("Hạn nộp đề cương?")).toBeInTheDocument();
    expect(socket.sent.at(-1)).toMatchObject({ type: "ask", question: "Hạn nộp đề cương?" });
    expect(screen.getByRole("button", { name: "Dừng" })).toBeInTheDocument();

    act(() => {
      socket.receive(turnFrame("status", "t1", { step: "searching", text: "tìm" }));
      socket.receive(turnFrame("tool_call", "t1", { name: "search_policy", label: "Tra cứu quy chế" }));
      socket.receive(turnFrame("tool_result", "t1", { name: "search_policy", ok: true, summary: "Tìm thấy 3 đoạn" }));
      socket.receive(turnFrame("token", "t1", { delta: "Nộp trong 2 tuần [cite:QC-" }));
    });
    expect(screen.getByText("Đang tra cứu quy chế")).toBeInTheDocument();
    expect(screen.getByText(/Gọi: Tra cứu quy chế/)).toBeInTheDocument();
    expect(screen.getByText(/Xong: Tìm thấy 3 đoạn/)).toBeInTheDocument();
    // Mảnh [cite: dở dang không lộ ra khi đang stream.
    expect(screen.getByText(/Nộp trong 2 tuần/).textContent).not.toContain("[cite");

    act(() => socket.receive(finalFrame("t1")));
    expect(screen.queryByRole("button", { name: "Dừng" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gửi" })).toBeDisabled();

    // Cảnh báo văn bản mẫu vì citation is_sample.
    expect(screen.getByText(/văn bản mẫu/)).toBeInTheDocument();

    const chips = screen.getAllByRole("button", { name: "Điều 5 khoản 2 · QC-01" });
    expect(chips.length).toBe(2); // một trong câu trả lời, một trong danh sách căn cứ
    expect(screen.queryByLabelText("Nguyên văn trích dẫn")).not.toBeInTheDocument();
    await user.click(chips[0]);
    const panel = screen.getByLabelText("Nguyên văn trích dẫn");
    expect(within(panel).getByText(CITATION.quote)).toBeInTheDocument();
    expect(within(panel).getByText(/Quy chế thực tập \(mẫu\)/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Đóng nguyên văn" }));
    expect(screen.queryByLabelText("Nguyên văn trích dẫn")).not.toBeInTheDocument();
  });

  it("nút Dừng gửi cancel; lượt hiện đã dừng", async () => {
    const user = userEvent.setup();
    renderChat();
    const socket = await sendQuestion(user, "hỏi");
    await user.click(screen.getByRole("button", { name: "Dừng" }));
    expect(socket.sent.at(-1)).toEqual({ type: "cancel", turn_id: "t1" });
    act(() => socket.receive(turnFrame("error", "t1", { code: "cancelled", message: "x" })));
    expect(screen.getByText("Bạn đã dừng câu trả lời này.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gửi" })).toBeInTheDocument();
  });

  it("cảnh báo degraded và kết luận no_match", async () => {
    const user = userEvent.setup();
    renderChat();
    const socket = await sendQuestion(user, "hỏi");
    act(() =>
      socket.receive(finalFrame("t1", { answer: "Không có căn cứ.", citations: [], verdict: "no_match", degraded: true })),
    );
    expect(screen.getByText(/Chế độ hạn chế/)).toBeInTheDocument();
    expect(screen.getByText(/Không tìm thấy căn cứ phù hợp/)).toBeInTheDocument();
  });

  it.each([
    ["busy", /đang xử lý một câu hỏi khác/],
    ["rate_limited", /quá nhanh/],
    ["timeout", /quá lâu/],
    ["llm_unavailable", /AI tạm thời không khả dụng/],
  ] as const)("lỗi %s hiện thông báo tiếng Việt", async (code, pattern) => {
    const user = userEvent.setup();
    renderChat();
    const socket = await sendQuestion(user, "hỏi");
    act(() => socket.receive(turnFrame("error", "t1", { code, message: "chi tiết" })));
    expect(screen.getByRole("alert")).toHaveTextContent(pattern);
  });

  it("trích dẫn không có trong danh sách không bấm được", async () => {
    const user = userEvent.setup();
    renderChat();
    const socket = await sendQuestion(user, "hỏi");
    act(() => socket.receive(finalFrame("t1", { answer: "Theo [cite:bia-ra].", citations: [] })));
    expect(screen.getByText("nguồn chưa xác minh").tagName).toBe("SPAN");
  });

  it("không dựng HTML từ nội dung câu trả lời", async () => {
    const user = userEvent.setup();
    const { container } = renderChat();
    const socket = await sendQuestion(user, "hỏi");
    act(() =>
      socket.receive(finalFrame("t1", { answer: "<img src=x onerror=alert(1)> **đậm**", citations: [] })),
    );
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("đậm").tagName).toBe("STRONG");
  });

  it("danh sách hội thoại cũ: mở một hội thoại hiển thị lịch sử có chip trích dẫn", async () => {
    const user = userEvent.setup();
    renderChat();
    const list = within(await screen.findByRole("navigation", { name: "Hội thoại" }));
    await user.click(await list.findByRole("button", { name: /Hạn nộp đề cương/ }));
    expect(await screen.findByText("Câu hỏi cũ")).toBeInTheDocument();
    expect(screen.getByText(/Chế độ hạn chế/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Điều 5 khoản 2 · QC-01" })[0]);
    expect(screen.getByLabelText("Nguyên văn trích dẫn")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Hội thoại mới" }));
    expect(screen.queryByText("Câu hỏi cũ")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Nguyên văn trích dẫn")).not.toBeInTheDocument();
  });

  it("Enter gửi câu hỏi, Shift+Enter không gửi", async () => {
    const user = userEvent.setup();
    renderChat();
    const box = screen.getByLabelText("Câu hỏi");
    await user.type(box, "a{Shift>}{Enter}{/Shift}b");
    expect(FakeSocket.instances).toHaveLength(0);
    await user.type(box, "{Enter}");
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
    expect(screen.getByText(/^a\s*b$/)).toBeInTheDocument();
  });
});
