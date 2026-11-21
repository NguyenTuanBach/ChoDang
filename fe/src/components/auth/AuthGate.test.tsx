import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AuthGate from "./AuthGate";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const USER = { id: "3", email: "sv.a@example.test", full_name: "Sinh viên A (mẫu)", role: "student" };

function fetchWith(handler: (url: string, init?: RequestInit) => Response) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init)) as unknown as typeof fetch;
}

describe("AuthGate", () => {
  beforeEach(() => replace.mockClear());

  it("hiện nội dung, tên và vai trò khi đã đăng nhập", async () => {
    render(
      <AuthGate fetchImpl={fetchWith(() => new Response(JSON.stringify(USER)))}>
        <p>Nội dung trang</p>
      </AuthGate>,
    );
    expect(await screen.findByText("Nội dung trang")).toBeInTheDocument();
    expect(screen.getByText("Sinh viên A (mẫu)")).toBeInTheDocument();
    expect(screen.getByText("Sinh viên")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("chuyển sang /login và không lộ nội dung khi chưa đăng nhập (401)", async () => {
    render(
      <AuthGate fetchImpl={fetchWith(() => new Response("{}", { status: 401 }))}>
        <p>Nội dung trang</p>
      </AuthGate>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Nội dung trang")).not.toBeInTheDocument();
  });

  it("báo lỗi (không chuyển trang) khi BE lỗi", async () => {
    render(
      <AuthGate fetchImpl={fetchWith(() => new Response(JSON.stringify({ message: "Lỗi hệ thống" }), { status: 500 }))}>
        <p>Nội dung trang</p>
      </AuthGate>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Lỗi hệ thống");
    expect(replace).not.toHaveBeenCalled();
  });

  it("đăng xuất gọi BE rồi về /login", async () => {
    const calls: string[] = [];
    const fetchImpl = fetchWith((url, init) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      return url === "/api/auth/me" ? new Response(JSON.stringify(USER)) : new Response(null, { status: 204 });
    });
    render(
      <AuthGate fetchImpl={fetchImpl}>
        <p>Nội dung trang</p>
      </AuthGate>,
    );
    await userEvent.setup().click(await screen.findByRole("button", { name: "Đăng xuất" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(calls).toContain("POST /api/auth/logout");
  });
});
