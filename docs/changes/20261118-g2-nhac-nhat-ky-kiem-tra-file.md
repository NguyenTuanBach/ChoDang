# Nhóm 2 — Nhắc SV ghi nhật ký tuần, kiểm tra file minh chứng mở được khi upload

> Ngày: 2026-11-18 · Branch `feature/g2-priority-reminder-ai-evidence`.

## Vấn đề

1. **SV bỏ sót nhật ký tuần nhưng hệ thống phát hiện quá muộn.** Hiện chỉ có rule `low_hours`: tổng giờ < 80% kỳ vọng, và chỉ xét sau 2 tuần. Điều 8 Khoản 1 quy định SV ghi nhật ký **hằng tuần**.
2. **Upload chỉ kiểm tra magic bytes**, nên file hỏng (ví dụ "PDF" 82 byte, không có trang nào) vẫn lọt qua. Đến lúc GV mở xem mới thấy lỗi.

## Đã làm

| Việc | File |
|---|---|
| Rule monitor `weekly_log_missing`, id `log_missing`, mức `info` (chỉ SV nhận thông báo), có căn cứ Điều 8 Khoản 1. Tuần N kết thúc ở ngày start + 7N; sau `grace_days` (2) ngày mà chưa có nhật ký thì nhắc. Không tính các tuần sau ngày kết thúc thực tập | `src/workflow/rules.py` (`missing_log_weeks`, `_log_missing`), `config/cohort.yaml` |
| Câu nhắc chỉ ghi "quy chế yêu cầu ghi nhật ký hằng tuần". Con số 2 ngày là độ trễ trước khi nhắc, **không phải hạn trong quy chế**, nên không được viết như luật | `rules.py` |
| Monitor cập nhật lại lý do của cờ đang mở khi nội dung đổi (ví dụ "tuần 5" thành "tuần 5, 6", hoặc cờ quá hạn tăng số ngày), không gửi thông báo lại. Trước đây lý do bị giữ nguyên như lúc tạo | `src/services/monitor.py` |
| `GET /internships/{id}/logs/missing` (cùng luật với cờ). Nếu khoa tắt rule thì trả về rỗng | `src/api/vin15/progress_routes.py` |
| Trang Nhật ký của SV: banner "Bạn chưa ghi nhật ký tuần …" kèm căn cứ; ô "Tuần" điền sẵn tuần thiếu sớm nhất | `frontend/src/features/student/StudentLogs.jsx` |
| `storage.check_readable()`, gọi trong `save_file`, áp dụng cho minh chứng và đính kèm nhật ký: PDF phải mở được, có ít nhất 1 trang và không đặt mật khẩu (pypdf); DOCX phải có `word/document.xml`; ảnh phải qua `Image.verify()` (Pillow). Lỗi trả 422 kèm lý do tiếng Việt. **Không** đổi `check_file`, nên luồng intake của nhóm 1 giữ nguyên | `src/services/storage.py` |
| Preview tái sử dụng `pdf_problem()` và hiện lý do cụ thể cho file cũ bị hỏng | `progress_routes.py`, `EvidencePreview.jsx` |

## Cách kiểm tra

- `pytest tests/`: **197 passed**, ruff sạch. Các test mới:
  - mốc thời gian nhắc (ngày 36 chưa nhắc, ngày 37 thì nhắc);
  - nhắc 1 lần → cờ cập nhật thành "tuần 5, 6" mà không nhắc lại → ghi bù xong thì cờ tự đóng;
  - endpoint `/logs/missing` có kiểm tra phạm vi truy cập;
  - upload từ chối PDF hỏng, PDF có mật khẩu, DOCX giả, ảnh hỏng; file hợp lệ vẫn qua.
- Các test cũ đang upload "PDF" giả đã được đổi sang PDF hợp lệ (`seed._demo_pdf`).
- Trình duyệt (`tests/ui/queue-preview-check.mjs`): **38/38 PASS**, gồm:
  - sv04 upload PDF hỏng qua giao diện → 422, toast "File PDF bị hỏng — hãy xuất lại file PDF rồi tải lên", file không xuất hiện trong danh sách;
  - trang Nhật ký của sv03 (dữ liệu thật, đủ tuần) không có banner;
  - với **response giả lập** thiếu tuần 3 và 4: banner hiện đúng, kèm căn cứ, ô tuần điền sẵn 3.
- Ảnh chụp đầu tiên cho thấy dòng căn cứ dính liền vào câu ("…ghi bù.Căn cứ"); đã sửa.

## Chưa kiểm tra / lưu ý

- **DB dev đã được đồng bộ `cohort.rules` từ YAML** để bật `log_missing` và `request_grace_days`. Trước khi đồng bộ đã so sánh: DB chỉ khác YAML ở đúng các khóa mới của nhóm 2. DB khác (staging/prod) cũng cần đồng bộ, hoặc seed lại; nếu không, rule mới không chạy.
- **Hiện không SV nào thiếu tuần**, nên banner trên web mới được kiểm bằng response giả lập. Luật thật đã được test ở backend.
- Rule đang để mức `info`, nên GV không nhận thông báo, nhưng vẫn thấy cờ ở trang Cảnh báo. Muốn báo cả GV khi SV thiếu từ 2 tuần trở lên thì cần thêm rule mức `warning`.
- Kiểm tra PDF bằng pypdf có tốn thêm thời gian với file lớn (≤ 10 MB), chưa đo.
