import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSession } from "@/lib/user-context";
import AuthProvider from "./AuthProvider";
import RoleGuard from "./RoleGuard";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }), usePathname: () => "/student" }));

const USER = { id: "3", email: "sv.a@example.test", full_name: "Sinh viên A (mẫu)", role: "student" };

function fetchWith(handler: (url: string, init?: RequestInit) => Response) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init)) as unknown as typeof fetch;
}

function WhoAmI() {
  const { user, unread, signOut } = useSession();
  return (
    <div>
      <p>
        {user.full_name} · {user.role} · chưa đọc {unread}
      </p>
      <button onClick={() => void signOut()}>Đăng xuất</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => replace.mockClear());

  it("cung cấp người dùng và số thông báo chưa đọc khi đã đăng nhập", async () => {
    const fetchImpl = fetchWith((url) => (url === "/api/auth/me" ? new Response(JSON.stringify(USER)) : new Response(JSON.stringify({ unread: 4 }))));
    render(
      <AuthProvider fetchImpl={fetchImpl}>
        <WhoAmI />
      </AuthProvider>,
    );
    expect(await screen.findByText(/Sinh viên A \(mẫu\) · student · chưa đọc/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/chưa đọc 4/)).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });

  it("chuyển sang /login và không lộ nội dung khi chưa đăng nhập (401)", async () => {
    render(
      <AuthProvider fetchImpl={fetchWith(() => new Response("{}", { status: 401 }))}>
        <p>Nội dung trang</p>
      </AuthProvider>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Nội dung trang")).not.toBeInTheDocument();
  });

  it("báo lỗi (không chuyển trang) khi BE lỗi", async () => {
    render(
      <AuthProvider fetchImpl={fetchWith(() => new Response(JSON.stringify({ message: "Lỗi hệ thống" }), { status: 500 }))}>
        <p>Nội dung trang</p>
      </AuthProvider>,
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
      <AuthProvider fetchImpl={fetchImpl}>
        <WhoAmI />
      </AuthProvider>,
    );
    await userEvent.setup().click(await screen.findByRole("button", { name: "Đăng xuất" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(calls).toContain("POST /api/auth/logout");
  });
});

describe("RoleGuard", () => {
  beforeEach(() => replace.mockClear());
  const me = fetchWith((url) => (url === "/api/auth/me" ? new Response(JSON.stringify(USER)) : new Response(JSON.stringify({ unread: 0 }))));

  it("hiện nội dung khi vai trò được phép", async () => {
    render(
      <AuthProvider fetchImpl={me}>
        <RoleGuard roles={["student"]}>
          <p>Trang sinh viên</p>
        </RoleGuard>
      </AuthProvider>,
    );
    expect(await screen.findByText("Trang sinh viên")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("đưa về trang chủ của vai trò và không lộ nội dung khi vai trò không được phép", async () => {
    render(
      <AuthProvider fetchImpl={me}>
        <RoleGuard roles={["admin"]}>
          <p>Trang quản trị</p>
        </RoleGuard>
      </AuthProvider>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/student"));
    expect(screen.queryByText("Trang quản trị")).not.toBeInTheDocument();
  });
});
