// Gọi BE cho trợ lý hỏi đáp: URL WebSocket, vé WebSocket, danh sách và nội dung hội thoại.
// Chỉ nói chuyện với BE (cùng origin qua rewrites, hoặc NEXT_PUBLIC_BE_WS_URL cho WebSocket).
import type { ConversationDetail, ConversationSummary } from "@/lib/assistant-protocol";
import type { UiErrorCode } from "./reducer";

const WS_PATH = "/api/assistant/ws";

export class AssistantError extends Error {
  constructor(
    public readonly code: UiErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "AssistantError";
  }
}

// NEXT_PUBLIC_BE_WS_URL có thể là gốc ("ws://localhost:8000") hoặc đủ đường dẫn; trống → cùng origin.
export function resolveWsUrl(
  base: string | undefined = process.env.NEXT_PUBLIC_BE_WS_URL,
  location: Pick<Location, "protocol" | "host"> = window.location,
): string {
  const configured = base?.trim();
  if (configured) {
    const url = new URL(configured);
    if (url.pathname === "/" || url.pathname === "") url.pathname = WS_PATH;
    return url.toString();
  }
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}${WS_PATH}`;
}

type Fetch = typeof fetch;

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    if (body.error?.message) return body.error.message;
  } catch {
    // không phải JSON: dùng mô tả mặc định
  }
  return `HTTP ${response.status}`;
}

export async function requestWsTicket(fetchImpl: Fetch = fetch): Promise<string> {
  let response: Response;
  try {
    response = await fetchImpl("/api/assistant/ws-ticket", { method: "POST", cache: "no-store" });
  } catch (error) {
    throw new AssistantError("ticket_failed", error instanceof Error ? error.message : "Không kết nối được BE");
  }
  if (!response.ok) {
    const code: UiErrorCode = response.status === 429 ? "rate_limited" : "ticket_failed";
    throw new AssistantError(code, await readError(response));
  }
  const body = (await response.json()) as { ticket?: string };
  if (!body.ticket) throw new AssistantError("ticket_failed", "BE không trả vé WebSocket");
  return body.ticket;
}

export async function listConversations(fetchImpl: Fetch = fetch): Promise<ConversationSummary[]> {
  const response = await fetchImpl("/api/assistant/conversations", { cache: "no-store" });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as ConversationSummary[];
}

export async function getConversation(id: string, fetchImpl: Fetch = fetch): Promise<ConversationDetail> {
  const response = await fetchImpl(`/api/assistant/conversations/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as ConversationDetail;
}
