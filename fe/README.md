# fe — frontend VIN-15 (Next.js)

Next.js (App Router, TypeScript), chạy ở cổng `3000`. Nói chuyện với BE (`be/`, cổng 8000) qua HTTP.
Phiên bản Next này khác bản quen thuộc: đọc `node_modules/next/dist/docs/` trước khi viết code (xem `AGENTS.md`).

## Chạy
```sh
npm ci
npm run dev                  # http://localhost:3000 (BE phải chạy ở localhost:8000, hoặc đặt BE_URL)
npm run lint && npx tsc --noEmit
npm test                     # vitest (jsdom)
npm run mock-be              # BE giả (cổng 8000) để xem /assistant khi BE thật chưa chạy
```
Hoặc chạy cả BE, agent và FE bằng `scripts/start.sh` ở gốc repo.

## Liên kết với BE
- `next.config.ts` có `rewrites`: `/api/:path*` → `${BE_URL}/api/:path*` (`BE_URL` mặc định `http://localhost:8000`).
  Trình duyệt chỉ gọi `/api/...` cùng origin với FE nên không vướng CORS; `BE_URL` chỉ nằm phía server.
- Server Component gọi thẳng BE bằng `getFromBackend` trong `src/lib/api.ts`.
- Trang chủ là trang kiểm tra kết nối: `ServerStatus` (server gọi `/api/health/readiness` và `/api/agent/health`)
  và `ClientPing` (trình duyệt gọi `/api/health` qua proxy).

## Trợ lý hỏi đáp (`/assistant`)
- Mã: `src/lib/assistant/` (`reducer.ts` trạng thái theo `turn_id`, `useAssistant.ts` hook WebSocket, `client.ts` ticket/REST/URL WS,
  `markdown.ts` bộ Markdown nhỏ không sinh HTML), `src/components/assistant/` (giao diện), khung hợp đồng ở `src/lib/assistant-protocol.ts`.
- Luồng: `POST /api/assistant/ws-ticket` → mở WS → `auth{ticket}` → `ready` → `ask`. Mất kết nối giữa lượt: nối lại (backoff 1/2/4/8/16 s,
  vé mới), rồi `GET /api/assistant/conversations/{id}` để lấy câu trả lời BE đã lưu.
- URL WebSocket: `NEXT_PUBLIC_BE_WS_URL` nếu đặt (gốc như `ws://localhost:8000` hoặc đủ đường dẫn), không thì cùng origin `/api/assistant/ws`.
- **`rewrites` có chuyển WebSocket**: đã thử với `next start`: handshake, khung và header `Origin`
  của trình duyệt đi qua proxy của Next tới BE. Lưu ý `BE_URL` được cố định lúc `next build` (đổi `BE_URL` phải build lại).
  Vì vậy `NEXT_PUBLIC_BE_WS_URL` chỉ cần khi triển khai mà proxy phía trước Next không giữ WebSocket.
- Test: `npm test` (reducer, hook với WebSocket giả, Markdown, thành phần chat).
