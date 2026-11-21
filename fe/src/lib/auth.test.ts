import { describe, expect, it, vi } from "vitest";
import { devLogin, fetchMe, listDevAccounts, logout } from "./auth";

const respond = (status: number, body?: unknown) =>
  vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })) as unknown as typeof fetch;

describe("auth client", () => {
  it("fetchMe: 401 -> null, 200 -> người dùng, lỗi khác -> ném", async () => {
    expect(await fetchMe(respond(401, {}))).toBeNull();
    expect(await fetchMe(respond(200, { id: "1", email: "a@x", full_name: "A", role: "admin" }))).toMatchObject({ role: "admin" });
    await expect(fetchMe(respond(503, { message: "DB sập" }))).rejects.toThrow("DB sập");
  });

  it("listDevAccounts: 404 (production) -> null", async () => {
    expect(await listDevAccounts(respond(404, {}))).toBeNull();
    expect(await listDevAccounts(respond(200, []))).toEqual([]);
  });

  it("devLogin gửi POST JSON, lỗi thì ném thông điệp của BE", async () => {
    const fetchImpl = respond(200, { id: "2", email: "gv@example.test", full_name: "GV", role: "lecturer" });
    await devLogin("gv@example.test", fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/auth/dev-login",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ email: "gv@example.test" }) }),
    );
    await expect(devLogin("x@y.z", respond(403, { message: "Chỉ tài khoản mẫu" }))).rejects.toThrow("Chỉ tài khoản mẫu");
  });

  it("logout: 204 ok, lỗi thì ném", async () => {
    await expect(logout(respond(204))).resolves.toBeUndefined();
    await expect(logout(respond(500, {}))).rejects.toThrow();
  });
});
