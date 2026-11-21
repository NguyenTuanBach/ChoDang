import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { API } from "../../lib/config";
import Login from "./Login";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
vi.mock("../../components/ui/ThemeToggle", () => ({ default: () => null }));
const login = vi.fn();
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ login }) }));

const setup = ({ oidc = { enabled: false } } = {}) => {
  api.mockImplementation(async (_m, path) => {
    if (path === "/auth/oidc/config") { if (oidc instanceof Error) throw oidc; return oidc; }
    return {};
  });
  render(<ToastProvider><Login /></ToastProvider>);
  return userEvent.setup();
};

beforeEach(() => {
  api.mockReset();
  login.mockReset();
});

describe("Login — form đăng nhập", () => {
  it("có ô tên đăng nhập, mật khẩu (che ký tự) và nút Đăng nhập", () => {
    setup();
    expect(screen.getByLabelText("Tên đăng nhập")).toBeRequired();
    expect(screen.getByLabelText("Mật khẩu")).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "Đăng nhập" })).toBeEnabled();
  });

  it("gửi đúng tên đăng nhập và mật khẩu đã nhập", async () => {
    login.mockResolvedValue();
    const user = setup();
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv03");
    await user.type(screen.getByLabelText("Mật khẩu"), "demo123");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    await waitFor(() => expect(login).toHaveBeenCalledWith("sv03", "demo123"));
  });

  it("để trống thì không gọi đăng nhập", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(login).not.toHaveBeenCalled();
  });

  it("đang đăng nhập thì khóa nút và đổi chữ; xong thì mở lại", async () => {
    let finish;
    login.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const user = setup();
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv03");
    await user.type(screen.getByLabelText("Mật khẩu"), "demo123");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("button", { name: "Đang đăng nhập…" })).toBeDisabled();
    finish();
    expect(await screen.findByRole("button", { name: "Đăng nhập" })).toBeEnabled();
  });

  it("sai mật khẩu → hiện lỗi từ máy chủ, giữ nguyên ô nhập và cho thử lại", async () => {
    login.mockRejectedValue(new Error("Sai tên đăng nhập hoặc mật khẩu"));
    const user = setup();
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv03");
    await user.type(screen.getByLabelText("Mật khẩu"), "sai");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Sai tên đăng nhập hoặc mật khẩu");
    expect(screen.getByLabelText("Tên đăng nhập")).toHaveValue("sv03");
    expect(screen.getByRole("button", { name: "Đăng nhập" })).toBeEnabled();
  });

  it("tài khoản bị khóa tạm thời cũng hiện nguyên thông báo của máy chủ", async () => {
    login.mockRejectedValue(new Error("Tài khoản tạm khóa, thử lại sau 15 phút"));
    const user = setup();
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv05");
    await user.type(screen.getByLabelText("Mật khẩu"), "x");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("status")).toHaveTextContent("tạm khóa");
  });
});

describe("Login — tài khoản demo", () => {
  it.each([["sv03 · Sinh viên", "sv03"], ["gv01 · Giảng viên", "gv01"], ["admin · Quản trị", "admin"]])(
    "bấm %s điền sẵn tên đăng nhập và mật khẩu demo", async (label, username) => {
      const user = setup();
      await user.click(screen.getByRole("button", { name: label }));
      expect(screen.getByLabelText("Tên đăng nhập")).toHaveValue(username);
      expect(screen.getByLabelText("Mật khẩu")).toHaveValue("demo123");
    },
  );
});

describe("Login — SSO", () => {
  it("chưa cấu hình SSO thì không có nút SSO", async () => {
    setup({ oidc: { enabled: false } });
    await waitFor(() => expect(api).toHaveBeenCalledWith("GET", "/auth/oidc/config"));
    expect(screen.queryByRole("link", { name: /SSO/ })).not.toBeInTheDocument();
  });

  it("bật SSO thì hiện nút dẫn tới endpoint đăng nhập OIDC", async () => {
    setup({ oidc: { enabled: true } });
    expect(await screen.findByRole("link", { name: /Đăng nhập bằng tài khoản trường \(SSO\)/ })).toHaveAttribute("href", `${API}/auth/oidc/login`);
  });

  it("không đọc được cấu hình SSO thì vẫn đăng nhập thường được", async () => {
    setup({ oidc: new Error("mất mạng") });
    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: /SSO/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Đăng nhập" })).toBeEnabled();
  });
});
