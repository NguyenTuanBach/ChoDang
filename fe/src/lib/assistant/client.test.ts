import { describe, expect, it, vi } from "vitest";
import { AssistantError, requestWsTicket, resolveWsUrl } from "./client";

const here = { protocol: "http:", host: "localhost:3000" };

describe("resolveWsUrl", () => {
  it("mặc định cùng origin (http → ws, https → wss)", () => {
    expect(resolveWsUrl("", here)).toBe("ws://localhost:3000/api/assistant/ws");
    expect(resolveWsUrl(undefined, { protocol: "https:", host: "app.example.edu" })).toBe(
      "wss://app.example.edu/api/assistant/ws",
    );
  });

  it("dùng NEXT_PUBLIC_BE_WS_URL: gốc thì thêm đường dẫn, đủ đường dẫn thì giữ nguyên", () => {
    expect(resolveWsUrl("ws://localhost:8000", here)).toBe("ws://localhost:8000/api/assistant/ws");
    expect(resolveWsUrl("ws://localhost:8000/", here)).toBe("ws://localhost:8000/api/assistant/ws");
    expect(resolveWsUrl("wss://be.example.edu/api/assistant/ws", here)).toBe("wss://be.example.edu/api/assistant/ws");
  });
});

describe("requestWsTicket", () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

  it("trả vé", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json({ ticket: "abc", expires_in: 30 }));
    await expect(requestWsTicket(fetchImpl)).resolves.toBe("abc");
    expect(fetchImpl).toHaveBeenCalledWith("/api/assistant/ws-ticket", expect.objectContaining({ method: "POST" }));
  });

  it("429 → rate_limited kèm thông điệp của BE", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json({ error: { code: "rate_limited", message: "Chậm lại" } }, 429));
    await expect(requestWsTicket(fetchImpl)).rejects.toMatchObject({ code: "rate_limited", message: "Chậm lại" });
  });

  it("lỗi khác và lỗi mạng → ticket_failed", async () => {
    await expect(requestWsTicket(vi.fn().mockResolvedValue(json({}, 500)))).rejects.toBeInstanceOf(AssistantError);
    await expect(requestWsTicket(vi.fn().mockRejectedValue(new Error("down")))).rejects.toMatchObject({
      code: "ticket_failed",
    });
  });
});
