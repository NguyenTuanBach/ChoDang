# Nhóm 2 — Hàng chờ hiện mốc đã nộp và nhật ký; xem minh chứng trực tiếp trên web

> Ngày: 2026-11-18 · Branch `feature/g2-tz-overdue-perf` · F4 (mốc, minh chứng, nhật ký).

## Vấn đề

1. **Hàng chờ duyệt không hiện những gì SV đã nộp.** `GET /approvals/queue` chỉ lấy hồ sơ `submitted`, đề cương `submitted` và gia hạn `open`, mà bỏ sót **mốc `submitted`** và **nhật ký `pending`**.
   - Ví dụ trên DB thật: sv04 đã nộp mốc 8 và mốc 9 (kèm file `hand_calc.jpg`), nhưng gv01 chỉ thấy một yêu cầu gia hạn.
   - GV phải tự mở từng hồ sơ mới thấy các mốc này.
2. **GV muốn xem file ngay trên web**, không phải tải về. Trước đây link luôn trả `Content-Disposition: attachment`, nên bấm vào là file bị tải về.
3. **Khi test trên Chrome thật mới phát hiện:** PDF demo trong seed là file giả 82 byte. Nó có đầu `%PDF` nên qua được kiểm tra magic bytes, nhưng trình xem PDF chỉ hiện lỗi tiếng Anh "Failed to load PDF document".

## Đã làm

| Việc | File |
|---|---|
| `review_items()`: lấy mốc đã nộp (bỏ mốc gắn đề cương, vì mốc này duyệt theo đề cương) và nhật ký chờ duyệt của SV được phân công. Có eager-load để tránh N+1, và có `missing_evidence` (tên loại minh chứng còn thiếu) | `src/api/vin15/progress_routes.py` |
| `/approvals/queue` gộp thêm `milestones` và `logs`. Chỉ thêm 2 dòng vào file của nhóm 1 | `src/api/vin15/internship_routes.py` |
| `GET /evidence/{id}/preview` (cùng phạm vi truy cập với `/url`) trả `kind` theo từng trường hợp: `pdf` / `image` (kèm link ký `&inline=1`), `text` (DOCX: server trích chữ, tối đa 20.000 ký tự), `broken` (PDF không đọc được, kiểm bằng pypdf), `missing` (file mất trên đĩa), `none` | `progress_routes.py` |
| `/files/{id}?inline=1` trả `inline` **chỉ với PDF, PNG, JPEG**. DOCX luôn là `attachment`. Thêm header `X-Content-Type-Options: nosniff` và `Cache-Control: private, no-store` | `progress_routes.py` |
| Modal `EvidencePreview`: PDF nhúng bằng iframe (có thêm nút "Mở tab mới"), ảnh, chữ từ DOCX, kèm thông báo tiếng Việt cho file hỏng hoặc mất. Nút "Tải về" lấy link ký mới mỗi lần bấm, vì link chỉ có hiệu lực 5 phút. Đóng được bằng Esc, nút Đóng, hoặc click ra ngoài. Trên điện thoại modal chiếm toàn màn hình | `frontend/src/features/shared/EvidencePreview.jsx`, `EvidenceLink.jsx`, `styles/components.css` |
| Mọi `EvidenceLink` (hàng chờ, chi tiết hồ sơ, timeline SV, nhật ký) giờ mở modal xem file thay vì tải về | `EvidenceLink.jsx` |
| Hàng chờ chia nhóm: Hồ sơ, Đề cương, Mốc đã nộp, Xin gia hạn, Nhật ký tuần. Card mốc có cảnh báo "Thiếu minh chứng bắt buộc", danh sách file, ô Chấp nhận / Trả lại. `ReviewInline` được tách thành file riêng để dùng chung | `LecturerQueue.jsx`, `ReviewInline.jsx`, `InternshipDetail.jsx` |
| Caddy: `/api/v1/files/*` cho phép nhúng frame cùng origin (`frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`). Các trang khác vẫn giữ `DENY` | `deploy/Caddyfile` |
| Seed tạo PDF demo hợp lệ 1 trang (`_demo_pdf`) | `src/seed.py` |

## Cách kiểm tra

- Backend: `pytest tests/` cho kết quả **188 passed**, ruff sạch. Thêm các test sau trong `tests/test_vin15/test_progress_opt.py`:
  - hàng chờ hiện mốc và nhật ký, GV khác không thấy;
  - preview đúng với PDF, ảnh, DOCX và PDF hỏng;
  - `inline` chỉ áp dụng cho PDF và ảnh;
  - SV khác gọi preview thì nhận 403.
- **Trên Chrome thật (headless, click như người dùng)**: chạy `cd tests/ui && npm i && node queue-preview-check.mjs`, kết quả **23/23 PASS**. Ảnh chụp lưu ở `tests/ui/screens/g2-*.png`. Kịch bản gồm:
  1. gv01 đăng nhập bằng form. Hàng chờ có nhóm "Mốc đã nộp (2)" và "Nhật ký tuần (1)", có cảnh báo thiếu minh chứng. Bấm `hand_calc.jpg` thì ảnh hiện trong modal; Esc đóng modal.
  2. sv04 tải một PDF thật lên mốc "Nộp báo cáo cuối kỳ" qua giao diện. gv01 vào Sinh viên → hồ sơ sv04 → bấm file: PDF hiện trong trình xem của Chrome, response trả `inline`, iframe không bị chặn.
  3. gv02 mở `midterm_report.pdf` (file giả của seed cũ): hiện thông báo tiếng Việt "File PDF bị hỏng…".
  4. Ở màn 390px: không tràn ngang, modal chiếm toàn màn hình.
  5. Không có lỗi JS hay console ở mọi bước.

## Chưa kiểm tra / lưu ý

- **Script e2e có ghi dữ liệu:** mỗi lần chạy, sv04 upload thêm một file `e2e-<số>.pdf` vào mốc "Nộp báo cáo cuối kỳ" (không nộp mốc). Muốn sạch thì reset DB.
- **DB đang chạy vẫn giữ 3 PDF demo giả**, vì seed chỉ chạy trên DB rỗng. Các file này giờ hiện thông báo "bị hỏng". Sau khi reset DB (`docker compose down -v`), file demo sẽ xem được.
- **Chưa test qua Caddy (HTTPS).** Header trong Caddyfile mới chỉ được viết, chưa chạy thử. Muốn test thì `docker compose up -d proxy` rồi `BASE_URL=https://localhost node queue-preview-check.mjs`.
- **Trình duyệt trên điện thoại:** Chrome Android không hiển thị PDF trong iframe (iOS Safari chỉ hiện trang đầu). Nút "Mở tab mới" là lối thoát cho trường hợp này. Ảnh chụp 390px mới kiểm với file ảnh.
- **Lúc upload vẫn chưa kiểm tra PDF có đọc được không:** storage chỉ kiểm magic bytes. Có thể thêm pypdf vào `check_file` để chặn file hỏng ngay từ lúc SV nộp.
- **Preview DOCX chỉ có phần chữ**, không có bảng hay hình ảnh.
