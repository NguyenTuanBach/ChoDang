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

### Tải tệp đề cương (AI tự điền form)
- Form đề cương nhập **bốn trường** (Mục tiêu, Nhiệm vụ, Kế hoạch, Kết quả dự kiến; `fe/src/lib/outline-sections.ts`), ghép thành một văn bản có tiêu đề khi nộp; lỗi báo ngay dưới đúng trường.
- Nút **Tải tệp đề cương** (PDF, PNG/JPG, DOCX, TXT/MD) → popup xem trước → Tải lên → `POST /api/student/outlines/extract` → AI tách bốn phần và **điền vào form** (chưa nộp); phần không có trong tệp để trống.
- BE `OutlineReviewService.extract_file`: DOCX/TXT/MD tách chữ bằng `read_policy_file` rồi gửi agent dạng `text/plain`; PDF và ảnh gửi nguyên. Không lưu tệp. Chỉ khi hồ sơ đã được xác nhận.
- Agent: `IntakeExtractor` thêm `kind="outline"` (`OUTLINE_FIELDS`, giá trị tối đa 4000 ký tự, nhánh `text/plain`); `auto` vẫn chỉ phân loại giấy tiếp nhận / giấy xác nhận.
- **Đính kèm trong ngăn Trợ lý** (📎): `kind=auto` giờ nhận cả `outline` (agent `AUTO_KINDS`); BE `IntakeService.auto_intake` trả `kind="outline"`, `target_page="outline"` và bốn phần (không lưu gì);
  FE chuyển sang `/student/outline` và điền nháp vào form (`usePendingAutofill("outline")`). Trước đó đính kèm đề cương trong chat bị báo "Không nhận ra loại giấy".
- Thử thật: PNG mẫu `docs/samples/de-cuong-thuc-tap-SV-D.png` → đủ 4 phần; TXT hai phần → điền 2 phần và ghi chú thiếu Nhiệm vụ, Kết quả dự kiến; `.exe` bị từ chối.

### Hồ sơ sau khi nộp: chỉ sửa phần cá nhân
- Quyết định đã chọn: sau khi nộp, thông tin công ty (tên, MST, địa chỉ, phòng ban, người hướng dẫn, giấy tiếp nhận) và thời gian **khóa**; sinh viên vẫn sửa **vị trí, mô tả công việc, hình thức**.
- BE `PUT /api/student/internship/personal` (`InternshipService.update_personal`, `CaseRepository.update_personal`): chỉ khi `submitted | confirmed | in_progress`; không đổi trạng thái hay phiên bản; ghi audit trước/sau;
  trường ngoài ba trường trên bị bỏ qua; vị trí và mô tả không được để trống. Đường lưu nháp cũ vẫn chặn sau khi nộp (409).
- FE `InternshipForm`: ô công ty/thời gian bị khóa, ba ô cá nhân mở kèm nút "Lưu thông tin cá nhân"; hồ sơ đã kết thúc (`completed`...) khóa tất cả.

### Hồ sơ: một giấy tiếp nhận, kiểm tra gọn
- Mỗi hồ sơ chỉ giữ **một** giấy tiếp nhận: `CaseRepository.replace_document` thêm giấy mới và xóa giấy cũ cùng transaction, `InternshipService.upload_document` xóa tệp cũ khỏi kho (lỗi xóa tệp không làm hỏng). FE chỉ hiện giấy mới nhất, nút đổi thành "Tải giấy khác (thay thế)".
- Thẻ "Kiểm tra trước khi nộp" chỉ liệt kê mục **chưa đạt** (Lỗi / Lưu ý); mọi mục đạt thì một dòng xác nhận; form khác bản đã lưu thì báo "Có thay đổi chưa lưu" kèm nút "Lưu và kiểm tra lại" và khóa nút Nộp.
- Đối chiếu tên sinh viên trên giấy chấp nhận tên rút gọn/đầy đủ (`names_differ`), như giấy xác nhận.
- `GET /api/student/internship` khi chưa có hồ sơ trả đủ các danh sách rỗng (trước đó thiếu khiến trang sập).

### Lưu tệp đề cương đã tải
- Trước đây tải tệp đề cương chỉ để AI đọc (không lưu). Giờ tệp (PDF, ảnh, DOCX) được **lưu kèm phiên bản đề cương** khi nộp thành công: migration `V14__outline_file.sql` (cột `file_name/file_mime/file_size/file_key` ở bảng `outline`), `POST /api/student/outlines/{id}/file` (chỉ chủ hồ sơ, mỗi phiên bản một tệp), `GET /api/outlines/{id}/file` (chủ hồ sơ, GV phụ trách, QTV).
- FE: sau khi AI đọc tệp, tệp hiện như một thẻ tệp (có nút bỏ); bấm Nộp thì lưu kèm. Lỗi lưu tệp chỉ báo toast, không làm mất lần nộp. Phiên bản đã nộp (sinh viên và giảng viên) hiện thẻ tệp để tải. Tệp `.txt/.md` chỉ để AI đọc, không lưu. Đính kèm qua ngăn Trợ lý (không có trang đề cương mở sẵn) chưa lưu tệp.

### Khác
- `scripts/start.ps1`: bản PowerShell của `start.sh` (Windows), có `-SkipAgent`/`-SkipBe`/`-SkipFe`; tìm `uv.exe` thật vì `python -m uv` tự thoát ngay.
- Dữ liệu mẫu: Sinh viên D (hồ sơ đã xác nhận, chưa có đề cương) trong `dev_seed.py`; ảnh giấy xác nhận mẫu ở `docs/samples/`.

## Kiểm tra
- BE: test mới `test_withdraw_evidence.py`, `test_outline_review.py` (13 + 13 test, gồm đọc tệp đề cương); agent `test_outline_extract.py` (4 test), `ruff` các file đã sửa sạch. FE: `tsc`, `eslint` sạch, `EvidencePreviewDialog.test.tsx` (3 test) đạt.
- Agent: đã thêm endpoint, test danh sách agent cập nhật. 15 test cũ về Trợ lý điều hướng (`navigate.py`) lỗi từ trước, không thuộc phần này.
- Thử thật qua API: `ai-advice` (nhật ký), `outlines` với đề cương thiếu phần (báo đúng 3 lỗi + 3 góp ý AI + nhận xét tổng quát).

## Chưa kiểm tra / lưu ý
- Chưa mở các trang trên trình duyệt; chưa thử lưu đề cương thật qua API (chỉ test đơn vị); chưa có test cho form AI đọc giấy.
- Quy tắc "đủ bốn phần" dựa trên từ khóa; viết phần đó dưới tên khác hẳn sẽ bị báo thiếu.
- Tải giấy ở mốc khác M5 (vd báo cáo giữa kỳ) vẫn đọc theo bộ trường của giấy xác nhận nên nhiều trường sẽ trống.
