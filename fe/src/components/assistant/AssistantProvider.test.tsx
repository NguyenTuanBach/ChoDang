import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthUser } from "@/lib/auth";
import { FakeSocket, finalFrame } from "@/lib/assistant/testing";
import { UserContext } from "@/lib/user-context";
import AssistantPanel from "./AssistantPanel";
import AssistantProvider, { useAssistantContext } from "./AssistantProvider";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }), usePathname: () => "/student" }));

const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input);
  if (url === "/api/assistant/ws-ticket" && init?.method === "POST") return new Response(JSON.stringify({ ticket: "tk", expires_in: 30 }));
  if (url === "/api/assistant/conversations") return new Response("[]");
  return new Response("{}", { status: 404 });
}) as unknown as typeof fetch;

function student(role: AuthUser["role"] = "student"): AuthUser {
  return { id: "3", email: "u@example.test", full_name: "Người dùng", role };
}

function Probe() {
  const { open, toggle } = useAssistantContext();
  return (
    <button onClick={toggle} aria-label="đổi">
      {open ? "mở" : "đóng"}
    </button>
  );
}

function setup(role: AuthUser["role"] = "student") {
  return render(
    <UserContext.Provider value={student(role)}>
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
        <Probe />
        <AssistantPanel />
      </AssistantProvider>
    </UserContext.Provider>,
  );
}

async function ask(user: ReturnType<typeof userEvent.setup>, text: string): Promise<FakeSocket> {
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
  push.mockClear();
  window.localStorage.clear();
});

describe("AssistantProvider: điều hướng theo lời trợ lý", () => {
  it("lượt đang chạy có action navigate thì đi tới đúng trang của vai trò, đúng một lần", async () => {
    const user = userEvent.setup();
    setup("student");
    const socket = await ask(user, "mở trang đề cương");
    act(() => socket.receive(finalFrame("t1", { answer: "Mình đã mở trang Đề cương.", citations: [], actions: [{ type: "navigate", page: "outline", label: "Đề cương" }] })));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/student/outline"));
    expect(push).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: /Đã mở: Đề cương/ })).toHaveAttribute("href", "/student/outline");
  });

  it("khóa trang lạ hoặc của vai trò khác bị bỏ qua (không điều hướng)", async () => {
    const user = userEvent.setup();
    setup("student");
    const socket = await ask(user, "mở trang audit");
    act(() => socket.receive(finalFrame("t1", { answer: "Không có trang đó.", citations: [], actions: [{ type: "navigate", page: "audit", label: "Audit" }, { type: "navigate", page: "../admin", label: "x" }] })));
    await waitFor(() => expect(screen.getByText("Không có trang đó.")).toBeInTheDocument());
    expect(push).not.toHaveBeenCalled();
  });

  it("giảng viên dùng bảng khóa của giảng viên", async () => {
    const user = userEvent.setup();
    setup("lecturer");
    const socket = await ask(user, "mở cờ rủi ro");
    act(() => socket.receive(finalFrame("t1", { answer: "Đã mở.", citations: [], actions: [{ type: "navigate", page: "flags", label: "Cờ rủi ro" }] })));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/lecturer/flags"));
  });

  it("trang chi tiết hồ sơ và bộ lọc thành đúng URL", async () => {
    const user = userEvent.setup();
    setup("lecturer");
    const socket = await ask(user, "mở hồ sơ của An");
    act(() =>
      socket.receive(
        finalFrame("t1", { answer: "Đã mở.", citations: [], actions: [{ type: "navigate", page: "internship_detail", label: "Chi tiết hồ sơ", internship_id: 7, filters: null }] }),
      ),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/lecturer/internships/7"));
    expect(screen.getByRole("link", { name: /Đã mở: Chi tiết hồ sơ/ })).toHaveAttribute("href", "/lecturer/internships/7");
  });

  it("bộ lọc thành query string, khóa lạ bị bỏ", async () => {
    const user = userEvent.setup();
    setup("lecturer");
    const socket = await ask(user, "mở cờ đã giải quyết");
    act(() =>
      socket.receive(finalFrame("t1", { answer: "Đã mở.", citations: [], actions: [{ type: "navigate", page: "flags", label: "Cờ rủi ro", filters: { status: "resolved", evil: "x" } }] })),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/lecturer/flags?status=resolved"));
  });

  it("câu hỏi gửi kèm trang đang mở", async () => {
    const user = userEvent.setup();
    setup("student");
    const socket = await ask(user, "trang này để làm gì?");
    const frame = socket.sent.find((f) => f.type === "ask");
    expect(frame?.page).toEqual({ key: "overview" }); // usePathname giả = "/student"
  });

  it("câu trả lời không có action thì không điều hướng", async () => {
    const user = userEvent.setup();
    setup();
    const socket = await ask(user, "hỏi");
    act(() => socket.receive(finalFrame("t1")));
    await waitFor(() => expect(screen.getByRole("button", { name: "Gửi" })).toBeDisabled());
    expect(push).not.toHaveBeenCalled();
  });
});

describe("AssistantProvider: trạng thái ngăn", () => {
  it("nhớ trạng thái mở/đóng trong localStorage và Ctrl+J bật/tắt", async () => {
    const user = userEvent.setup();
    setup();
    expect(screen.getByRole("button", { name: "đổi" })).toHaveTextContent("đóng");
    await user.click(screen.getByRole("button", { name: "đổi" }));
    expect(screen.getByRole("button", { name: "đổi" })).toHaveTextContent("mở");
    expect(window.localStorage.getItem("vin15.assistant.open")).toBe("1");
    await user.keyboard("{Control>}j{/Control}");
    expect(screen.getByRole("button", { name: "đổi" })).toHaveTextContent("đóng");
    expect(window.localStorage.getItem("vin15.assistant.open")).toBe("0");
  });

  it("câu hỏi gợi ý theo vai trò gửi luôn khi bấm", async () => {
    const user = userEvent.setup();
    setup("lecturer");
    await user.click(screen.getByRole("button", { name: "Có bao nhiêu sinh viên đang bị chậm thực tập?" }));
    await waitFor(() => expect(FakeSocket.instances[0]).toBeDefined());
    expect(screen.getByText("Có bao nhiêu sinh viên đang bị chậm thực tập?", { selector: "div" })).toBeInTheDocument();
  });
});
