import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, getToken, setToken, setUnauthorizedHandler } from "../lib/api";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../lib/api", () => ({ api: vi.fn(), getToken: vi.fn(), setToken: vi.fn(), setUnauthorizedHandler: vi.fn() }));

const ME = { id: 3, role: "student", full_name: "Nguyễn Văn An" };
const CONFIG = { cohort: { name: "Học kỳ 1/2027" }, evidence_types: {} };

const server = ({ meError } = {}) => api.mockImplementation(async (method, path, body) => {
  if (path === "/auth/login") return { token: "tok-123", echoed: body };
  if (path === "/me") { if (meError) throw meError; return ME; }
  if (path === "/config") return CONFIG;
  return {};
});

const setup = () => renderHook(() => useAuth(), { wrapper: AuthProvider });

beforeEach(() => {
  api.mockReset();
  getToken.mockReset();
  setToken.mockReset();
  setUnauthorizedHandler.mockReset();
});

describe("AuthContext — khởi động", () => {
  it("chưa có token: không gọi API, chưa đăng nhập, không ở trạng thái đang tải", () => {
    getToken.mockReturnValue(null);
    const { result } = setup();
    expect(result.current).toMatchObject({ me: null, config: null, loading: false });
    expect(api).not.toHaveBeenCalled();
  });

  it("có token đã lưu: tải /me và /config rồi vào hệ thống", async () => {
    getToken.mockReturnValue("saved");
    server();
    const { result } = setup();
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.me).toEqual(ME);
    expect(result.current.config).toEqual(CONFIG);
  });

  it("token hết hạn hoặc sai: xóa token và về trạng thái chưa đăng nhập", async () => {
    getToken.mockReturnValue("stale");
    server({ meError: new Error("Phiên đăng nhập hết hạn") });
    const { result } = setup();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.me).toBeNull();
    expect(setToken).toHaveBeenCalledWith(null);
  });

  it("đăng ký xử lý 401: khi API báo hết phiên thì tự đăng xuất", async () => {
    getToken.mockReturnValue("saved");
    server();
    const { result } = setup();
    await waitFor(() => expect(result.current.me).toEqual(ME));
    const handler = setUnauthorizedHandler.mock.calls.at(-1)[0];
    act(() => handler());
    expect(result.current.me).toBeNull();
    expect(setToken).toHaveBeenCalledWith(null);
  });
});

describe("AuthContext — đăng nhập và đăng xuất", () => {
  it("login chuẩn hóa tên đăng nhập (cắt khoảng trắng, chữ thường), lưu token rồi tải hồ sơ", async () => {
    getToken.mockReturnValue(null);
    server();
    const { result } = setup();
    await act(() => result.current.login("  SV03 ", "demo123"));
    expect(api).toHaveBeenCalledWith("POST", "/auth/login", { username: "sv03", password: "demo123" });
    expect(setToken).toHaveBeenCalledWith("tok-123");
    expect(result.current.me).toEqual(ME);
    expect(result.current.config).toEqual(CONFIG);
  });

  it("login sai: ném lỗi cho form xử lý, không lưu token, vẫn chưa đăng nhập", async () => {
    getToken.mockReturnValue(null);
    api.mockRejectedValue(new Error("Sai tên đăng nhập hoặc mật khẩu"));
    const { result } = setup();
    await expect(act(() => result.current.login("sv03", "sai"))).rejects.toThrow("Sai tên đăng nhập hoặc mật khẩu");
    expect(setToken).not.toHaveBeenCalled();
    expect(result.current.me).toBeNull();
  });

  it("loginWithToken (callback SSO): lưu token từ URL rồi tải hồ sơ", async () => {
    getToken.mockReturnValue(null);
    server();
    const { result } = setup();
    await act(() => result.current.loginWithToken("sso-token"));
    expect(setToken).toHaveBeenCalledWith("sso-token");
    expect(result.current.me).toEqual(ME);
  });

  it("logout xóa token, hồ sơ và cấu hình", async () => {
    getToken.mockReturnValue("saved");
    server();
    const { result } = setup();
    await waitFor(() => expect(result.current.me).toEqual(ME));
    act(() => result.current.logout());
    expect(setToken).toHaveBeenLastCalledWith(null);
    expect(result.current).toMatchObject({ me: null, config: null, loading: false });
  });
});
