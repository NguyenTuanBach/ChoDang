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
- Trang chủ `/` chuyển người dùng về trang đầu của vai trò (`/student`, `/lecturer`, `/admin`). `ServerStatus`/`ClientPing` (kiểm tra kết nối) còn trong
  `src/components` nhưng không còn được trang nào dùng.

## Giao diện theo vai trò
- `AuthGate roles={[...]}` (`src/components/auth/AuthGate.tsx`) chặn người chưa đăng nhập, chuyển vai trò không phù hợp về trang chủ của họ, dựng menu (`src/lib/nav.ts`),
  số thông báo chưa đọc và cung cấp người dùng qua `useCurrentUser()`.
- Sinh viên `/student/*`: tổng quan, hồ sơ (AI gợi ý trường, kiểm trước khi nộp), đề cương, mốc và minh chứng, nhật ký, gia hạn/ngoại lệ, kết thúc và tín chỉ, bảng điểm LMS.
- Giảng viên `/lecturer/*`: hàng chờ, sinh viên (mời), hồ sơ (lọc, xuất CSV, chi tiết: xác nhận, duyệt, chấp nhận mốc, nhận xét, thẩm định, tiền thẩm AI), yêu cầu, cờ rủi ro.
- Quản trị viên `/admin/*`: hàng chờ, tài khoản (mời GV/SV, gán GV phụ trách, mã SV), hồ sơ, yêu cầu ảnh hưởng tín chỉ, phê duyệt tín chỉ, cấu hình (mốc mẫu, chuẩn đầu ra,
  loại ngoại lệ), LMS (học phần, tiên quyết, điểm, đồng bộ), audit. Dùng chung: `/dashboard`, `/notifications`, `/assistant`.
- Gọi API: `src/lib/http.ts` (`api`, `send`, `upload`), hook `useApi`/`useAction` (`src/lib/hooks.ts`), kiểu dữ liệu `src/lib/types.ts`, nhãn `src/lib/labels.ts`,
  thành phần dùng chung `src/components/ui/ui.tsx` (Tailwind CSS v4; màu trạng thái thống nhất: xanh = xong, vàng = chờ người khác, cam = cần bạn làm, đỏ = quá hạn/bị chặn, xám = chưa tới). `src/app/globals.css` giữ biến màu và kiểu nền cho thẻ nhập thô; chỉ `components/assistant/*` còn dùng CSS Modules. Bước nhập lý do bắt buộc dùng `DecisionPanel` (BR-S2).

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
