# Minh chứng (xem lại / thu hồi / AI đọc), tải giấy tiếp nhận, đề cương có AI quét

## Mục tiêu
Hoàn thiện luồng sinh viên tự tải, kiểm tra và sửa giấy tờ: xem trước khi tải, tự thu hồi khi tải nhầm, AI đọc giấy tự điền ở mọi bước,
đề cương được kiểm tra và nhận xét ngay khi nộp thay vì tích chuẩn đầu ra bằng tay.

## Đã làm
### Trang mốc `/student/milestones`
- `EvidencePreviewDialog.tsx`: chọn tệp → popup xem trước lớn (ảnh, PDF, liên kết "Mở tab mới") → "Tải lên" mới gửi. Popup dùng chung `ui/dialog.tsx` (thêm `wide`).
- **Thu hồi minh chứng**: nút dấu trừ cạnh dòng "Lần n" (chỉ minh chứng còn "Đã nộp, chờ duyệt" và mốc chưa nộp/chưa chấp nhận), popup xác nhận.
  BE `POST /api/student/evidence/{id}/withdraw` (`MilestoneService.withdraw_evidence`): chỉ chủ minh chứng, xóa dòng + tệp, ghi audit.
- Form "Thông tin trên giấy" (AI đọc, điền sẵn) có ở **mọi mốc**; tải PDF/ảnh xong AI đọc ngay, không hỏi lại; bỏ hiển thị nguồn và "AI 90%"; ô nhận xét to hơn.
- Các lần nộp hiện "Lần 1, Lần 2…" (thẻ, giờ nộp, lý do "Thất bại" nếu bị trả).

### Trang hồ sơ `/student/internship`
- Nút "Tải giấy tiếp nhận" luôn hiện (mờ kèm lý do khi hồ sơ đã nộp, vì BE không nhận thêm giấy sau khi nộp); chọn tệp → popup xem trước → Tải lên → AI đọc và **tự điền thẳng form**
  (chưa lưu, nút "Lưu bản nháp" nhấp nháy).

### Đề cương `/student/outline`
- Bỏ danh sách tích chuẩn đầu ra. Khi nộp, `OutlineReviewService`:
  1. luật cố định `outline_check.py`: đủ độ dài và đủ bốn phần Mục tiêu / Nhiệm vụ / Kế hoạch / Kết quả dự kiến; thiếu → **không lưu**, báo đúng phần sai;
  2. agent `outline_review` (`/v1/outline/review`, prompt `outline_review.system.md`): góp ý theo phần, nhận xét tổng quát, **nhận diện chuẩn đầu ra được phủ**;
  3. không lỗi → lưu, chuẩn đầu ra do AI nhận diện (chỉ giữ mã có trong khóa), nhận xét AI lưu ở `outline.ai_review` (migration `V13`).
- Agent tắt vẫn nộp được nếu đạt phần luật; nhận xét AI để trống.

### Khác
- `scripts/start.ps1`: bản PowerShell của `start.sh` (Windows), có `-SkipAgent`/`-SkipBe`/`-SkipFe`; tìm `uv.exe` thật vì `python -m uv` tự thoát ngay.
- Dữ liệu mẫu: Sinh viên D (hồ sơ đã xác nhận, chưa có đề cương) trong `dev_seed.py`; ảnh giấy xác nhận mẫu ở `docs/samples/`.

## Kiểm tra
- BE: test mới `test_withdraw_evidence.py`, `test_outline_review.py` (13 + 9 test), `ruff` các file đã sửa sạch. FE: `tsc`, `eslint` sạch, `EvidencePreviewDialog.test.tsx` (3 test) đạt.
- Agent: đã thêm endpoint, test danh sách agent cập nhật. 15 test cũ về Trợ lý điều hướng (`navigate.py`) lỗi từ trước, không thuộc phần này.
- Thử thật qua API: `ai-advice` (nhật ký), `outlines` với đề cương thiếu phần (báo đúng 3 lỗi + 3 góp ý AI + nhận xét tổng quát).

## Chưa kiểm tra / lưu ý
- Chưa mở các trang trên trình duyệt; chưa thử lưu đề cương thật qua API (chỉ test đơn vị); chưa có test cho form AI đọc giấy.
- Quy tắc "đủ bốn phần" dựa trên từ khóa; viết phần đó dưới tên khác hẳn sẽ bị báo thiếu.
- Tải giấy ở mốc khác M5 (vd báo cáo giữa kỳ) vẫn đọc theo bộ trường của giấy xác nhận nên nhiều trường sẽ trống.
