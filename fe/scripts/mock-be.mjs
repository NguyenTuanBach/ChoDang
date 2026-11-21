// BE giả để xem giao diện /assistant khi BE thật chưa sẵn (chỉ dùng khi dev).
//   npm run mock-be            # nghe cổng 8000 (PORT=... để đổi); chạy cùng `npm run dev`
// Giả lập: POST /api/assistant/ws-ticket, GET conversations, WS /api/assistant/ws (auth → ask → khung → final).
// Gõ câu có "mẫu" → căn cứ là văn bản mẫu; "lỗi" → error llm_unavailable; "chậm" → trả lời lâu để thử nút Dừng.
import { createServer } from "node:http";
import { WebSocketServer } from "ws";

const PORT = Number(process.env.PORT ?? 8000);
const tickets = new Set();
const conversations = new Map(); // id → {id,title,created_at,updated_at,messages[]}

const citation = (isSample) => ({
  chunk_id: "QC-01:v1:d5:k2",
  doc_code: "QC-01",
  doc_title: "Quy chế thực tập (mẫu)",
  version: "v1",
  article: "Điều 5",
  clause: "2",
  effective_from: "2026-01-01",
  is_sample: isSample,
  quote: "Sinh viên nộp đề cương thực tập trong vòng 02 tuần kể từ ngày bắt đầu thực tập.",
});

const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};

const server = createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (req.method === "POST" && url.pathname === "/api/assistant/ws-ticket") {
    const ticket = crypto.randomUUID();
    tickets.add(ticket);
    return json(res, 200, { ticket, expires_in: 30 });
  }
  if (req.method === "GET" && url.pathname === "/api/assistant/conversations") {
    return json(res, 200, [...conversations.values()].map((c) => ({ id: c.id, title: c.title, created_at: c.created_at, updated_at: c.updated_at })));
  }
  const match = url.pathname.match(/^\/api\/assistant\/conversations\/(.+)$/);
  if (req.method === "GET" && match) {
    const conversation = conversations.get(decodeURIComponent(match[1]));
    return conversation ? json(res, 200, conversation) : json(res, 404, { error: { code: "not_found", message: "Không có hội thoại" } });
  }
  if (url.pathname === "/api/health") return json(res, 200, { status: "UP", mock: true });
  json(res, 404, { error: { code: "not_found", message: "mock-be không có route này" } });
});

const wss = new WebSocketServer({ server, path: "/api/assistant/ws" });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

wss.on("connection", (ws, req) => {
  console.log("[mock-be] WS mở, Origin =", req.headers.origin);
  let authed = false;
  let cancelled = false;
  let busy = false;
  const send = (frame) => ws.readyState === 1 && ws.send(JSON.stringify(frame));
  const authTimer = setTimeout(() => !authed && ws.close(4401, "auth timeout"), 5000);

  ws.on("message", async (raw) => {
    const frame = JSON.parse(String(raw));
    if (!authed) {
      if (frame.type === "auth" && tickets.delete(frame.ticket)) {
        authed = true;
        clearTimeout(authTimer);
        return send({ type: "ready" });
      }
      return ws.close(4401, "bad ticket");
    }
    if (frame.type === "ping") return send({ type: "pong" });
    if (frame.type === "cancel") cancelled = true;
    if (frame.type !== "ask") return;
    if (busy) return send({ type: "error", code: "busy", message: "Đang có lượt chạy", turn_id: frame.turn_id });
    busy = true;
    cancelled = false;

    const id = frame.conversation_id ?? crypto.randomUUID();
    const scope = { turn_id: frame.turn_id, conversation_id: id };
    const slow = frame.question.includes("chậm");
    const now = new Date().toISOString();
    const conversation = conversations.get(id) ?? { id, title: frame.question.slice(0, 40), created_at: now, updated_at: now, messages: [] };
    conversations.set(id, conversation);
    conversation.messages.push({ id: crypto.randomUUID(), turn_id: frame.turn_id, role: "user", content: frame.question, citations: [], degraded: false, created_at: now });

    send({ type: "status", step: "planning", text: "Phân tích câu hỏi", ...scope });
    await sleep(400);
    send({ type: "tool_call", name: "search_policy", label: "Tra cứu quy chế", ...scope });
    await sleep(600);
    send({ type: "tool_result", name: "search_policy", ok: true, summary: "Tìm thấy 3 đoạn", ...scope });
    send({ type: "status", step: "answering", text: "Soạn câu trả lời", ...scope });

    if (frame.question.includes("lỗi")) {
      send({ type: "error", code: "llm_unavailable", message: "mock", ...scope });
      busy = false;
      return;
    }
    const answer = "**Hạn nộp đề cương** là trong vòng 02 tuần kể từ ngày bắt đầu thực tập [cite:QC-01:v1:d5:k2].\n\n- Nộp qua hệ thống\n- Giảng viên hướng dẫn duyệt";
    for (const word of answer.split(/(?<= )/)) {
      if (cancelled) break;
      send({ type: "token", delta: word, ...scope });
      await sleep(slow ? 400 : 40);
    }
    if (cancelled) {
      send({ type: "error", code: "cancelled", message: "Đã dừng", ...scope });
    } else {
      const citations = [citation(frame.question.includes("mẫu"))];
      conversation.messages.push({ id: crypto.randomUUID(), turn_id: frame.turn_id, role: "assistant", content: answer, citations, degraded: frame.question.includes("degraded"), created_at: new Date().toISOString() });
      send({ type: "final", answer, citations, verdict: "answered", degraded: frame.question.includes("degraded"), usage: {}, trace_id: "mock", message_id: "m", ...scope });
    }
    busy = false;
  });
  ws.on("close", () => clearTimeout(authTimer));
});

server.listen(PORT, () => console.log(`[mock-be] http://localhost:${PORT}`));
