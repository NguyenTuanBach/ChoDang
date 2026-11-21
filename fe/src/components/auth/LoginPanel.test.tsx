import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPanel from "./LoginPanel";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const ACCOUNTS = [
  { id: "1", email: "qtv@example.test", full_name: "Quản trị viên mẫu", role: "admin" },
  { id: "2", email: "gv@example.test", full_name: "Cô Lan (mẫu)", role: "lecturer" },
  { id: "3", email: "sv.a@example.test", full_name: "Sinh viên A (mẫu)", role: "student" },
];

function makeFetch(overrides: Partial<Record<string, Response>> = {}) {
  const calls: { url: string; body?: string }[] = [];
  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body as string | undefined });
    return overrides[url] ?? (url === "/api/auth/dev-accounts" ? new Response(JSON.stringify(ACCOUNTS)) : new Response("{}", { status: 404 }));
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

describe("LoginPanel", () => {
  beforeEach(() => replace.mockClear());

  it("liệt kê tài khoản dev theo vai trò và để nút Google ở trạng thái chưa bật", async () => {
    render(<LoginPanel fetchImpl={makeFetch().fetchImpl} />);
    const dev = await screen.findByRole("region", { name: "Đăng nhập dev" });
    for (const heading of ["Quản trị viên", "Giảng viên", "Sinh viên"]) {
      expect(within(dev).getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(within(dev).getAllByRole("button")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Đăng nhập Google" })).toBeDisabled();
  });

  it("bấm một tài khoản thì gọi dev-login đúng email rồi vào trang chủ", async () => {
    const { fetchImpl, calls } = makeFetch({ "/api/auth/dev-login": new Response(JSON.stringify(ACCOUNTS[1])) });
    render(<LoginPanel fetchImpl={fetchImpl} />);
    await userEvent.setup().click(await screen.findByRole("button", { name: /Cô Lan/ }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(JSON.parse(calls.find((c) => c.url === "/api/auth/dev-login")!.body!)).toEqual({ email: "gv@example.test" });
  });

  it("đăng nhập lỗi thì báo lỗi, ở lại trang và cho bấm lại", async () => {
    const { fetchImpl } = makeFetch({
      "/api/auth/dev-login": new Response(JSON.stringify({ message: "Tài khoản không hoạt động" }), { status: 401 }),
    });
    render(<LoginPanel fetchImpl={fetchImpl} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Sinh viên A/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Tài khoản không hoạt động");
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Sinh viên A/ })).toBeEnabled();
  });

  it("ẩn khối đăng nhập dev khi BE không bật (production trả 404)", async () => {
    const { fetchImpl } = makeFetch({ "/api/auth/dev-accounts": new Response("{}", { status: 404 }) });
    render(<LoginPanel fetchImpl={fetchImpl} />);
    await waitFor(() => expect(screen.queryByText("Đang tải...")).not.toBeInTheDocument());
    expect(screen.queryByRole("region", { name: "Đăng nhập dev" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đăng nhập Google" })).toBeInTheDocument();
  });
});
