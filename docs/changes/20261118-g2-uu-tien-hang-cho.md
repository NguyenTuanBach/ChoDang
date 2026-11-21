# Nhóm 2 — Sắp xếp hàng chờ duyệt theo độ ưu tiên

> Ngày: 2026-11-18 · Branch `feature/g2-priority-reminder-ai-evidence` · Tiếp nối `20261118-g2-hang-cho-xem-minh-chung.md`.

## Mục tiêu

GV có nhiều mục chờ duyệt (hồ sơ, đề cương, mốc, gia hạn, nhật ký). Cần đưa mục **gấp nhất** lên đầu, và mỗi mục phải nói rõ **vì sao** nó được xếp ở vị trí đó.

**Quyết định: tính điểm bằng luật, không dùng AI để xếp hạng.** Lý do:
- Thứ tự hiển thị ảnh hưởng tới việc đơn nào được xử lý trước, nên phải giải thích và test được (HITL).
- Muốn AI chấm "mức khẩn" thì phải gửi lý do cá nhân của SV sang model.
- Hệ thống phải chạy được khi không có API key (mock-first).

Điểm chỉ dùng để sắp xếp; không mục nào được tự duyệt hay tự từ chối.

## Đã làm

| Việc | File |
|---|---|
| Module tính điểm `PriorityContext`, mỗi mục trả về `{score, level, reasons, since}`. Cờ rủi ro được đếm bằng 1 query cho toàn bộ hàng chờ | `src/services/priority.py` (mới) |
| Trọng số khai báo trong `priority:`, thiếu khóa nào thì dùng `DEFAULTS` | `config/cohort.yaml` |
| Gắn `priority` cho cả 5 loại mục trong `/approvals/queue` | `internship_routes.py` (vài dòng), `progress_routes.review_items` |
| Nút chọn **Ưu tiên** (mặc định) / **Chờ lâu nhất** / **Theo loại**; lựa chọn lưu trong `localStorage` của từng người xem. Nhãn "Ưu tiên cao/vừa" và nhãn lý do hiện dưới tên SV. Mỗi card có `data-priority` để test | `LecturerQueue.jsx`, `styles/components.css` |

**Các luật tính điểm** (giá trị mặc định):

| Luật | Điểm |
|---|---|
| Điểm nền theo loại | gia hạn 20, hồ sơ 15, đề cương 15, mốc 10, nhật ký 0 |
| Hạn liên quan đã qua: mốc của đơn gia hạn, hạn đề cương | +50, kèm lý do "… đã quá hạn N ngày" |
| Hạn liên quan còn ≤ 3 ngày | +30 |
| Hồ sơ chờ duyệt có ngày bắt đầu còn ≤ 7 ngày (hoặc đã qua) | +30 (đã qua: +50) |
| Mỗi ngày chờ | +2, tối đa 20 |
| Mỗi cờ rủi ro mức warning/critical đang mở của SV | +10, tối đa 20 |
| Phân mức hiển thị | ≥ 50 là "cao", ≥ 25 là "vừa" |
| Hai mục bằng điểm | mục chờ lâu hơn đứng trước |

## Cách kiểm tra

- `pytest tests/`: **194 passed**, ruff sạch. Thêm `tests/test_vin15/test_priority.py`, kiểm tra:
  - đơn gia hạn cho mốc quá hạn đứng đầu, ở mức cao;
  - hồ sơ sắp bắt đầu có lý do tương ứng;
  - luật về hạn và giới hạn điểm thời gian chờ;
  - cờ rủi ro làm tăng điểm, lý do xếp theo trọng số;
  - trọng số đọc từ YAML;
  - chỉ đếm cờ của SV mình phụ trách.
- Trình duyệt (`tests/ui/queue-preview-check.mjs`): **31/31 PASS**, kiểm tra:
  - mặc định là chế độ "Ưu tiên";
  - thứ tự card khớp điểm từ API, giảm dần;
  - chuyển được giữa 3 chế độ;
  - chế độ "Theo loại" được nhớ sau khi tải lại trang;
  - gv03 thấy đề cương "Ưu tiên cao · Hạn đề cương đã quá hạn 16 ngày" ở đầu (ảnh `g2-gv03-queue-priority.png`).
- Trong lần chạy đầu, test đòi đơn gia hạn phải đứng đầu nhưng fail. Nguyên nhân: đơn gia hạn #1 của seed đã bị gv01 từ chối trong lúc test tay, theo audit. Đã sửa test để không phụ thuộc dữ liệu, chỉ so thứ tự trên trang với điểm từ API.

## Chưa kiểm tra / lưu ý

- Trọng số mới là đề xuất ban đầu, **chưa có GV thật dùng thử**. Có thể chỉnh trong `cohort.yaml` mà không phải sửa code.
- "Thời điểm bắt đầu chờ" của hồ sơ đang lấy `updated_at`, nên sẽ reset nếu hồ sơ bị sửa sau khi nộp. Muốn chính xác thì lấy từ audit `submitted`.
- Điểm chỉ áp dụng cho hàng chờ của GV; danh sách tổng hợp (`/internships-summary`) vẫn sắp xếp như cũ.
