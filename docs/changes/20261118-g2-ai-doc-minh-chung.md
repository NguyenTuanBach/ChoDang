# Nhóm 2 — AI hỗ trợ đọc minh chứng (gợi ý cho GV)

> Ngày: 2026-11-18 · Branch `feature/g2-priority-reminder-ai-evidence`.

## Vấn đề

AI trong hệ thống mới có ở 4 chỗ: trích xuất giấy tiếp nhận, tóm tắt đề cương, tóm tắt yêu cầu gia hạn, và trợ lý chính sách. **File minh chứng** (giấy tiếp nhận, báo cáo giữa kỳ / cuối kỳ, phiếu đánh giá) chưa có AI đọc, nên GV phải tự mở và đọc từng file.

## Nguyên tắc

- **Chỉ gợi ý.** Kết quả gắn nhãn "Gợi ý của AI — chỉ để tham khảo, GV là người quyết định". Không có luồng nào tự chấp nhận hay trả lại (HITL).
- **Che PII trước khi gửi model.** Thông tin bị thay bằng placeholder: tên SV, MSSV, email, SĐT; tên doanh nghiệp, mã số thuế, địa chỉ doanh nghiệp; tên, email, SĐT người hướng dẫn. Có test kiểm tra văn bản thực sự gửi đi.
- **Không khẳng định chữ ký, con dấu hay tính xác thực.** Luôn kèm câu giới hạn; nếu chữ được đọc bằng OCR thì ghi thêm "có thể sai".
- **Chạy được khi không có API key (mock-first).** Các kiểm tra theo luật vẫn chạy; phần tóm tắt dùng vài câu đầu của văn bản.
- **AI lỗi thì trả `None`.** UI hiện "Chưa có gợi ý AI", GV vẫn xem file và duyệt bình thường. Lỗi không được lưu cache, nên lần sau thử lại.
- **Checklist do khoa cấu hình.** Quy chế không quy định nội dung báo cáo giữa kỳ / cuối kỳ, nên các mục đó không gắn căn cứ. Chỉ giấy tiếp nhận (Điều 7 K1) và phiếu đánh giá (Điều 9 K1) có `citation`.

## Đã làm

| Việc | File |
|---|---|
| `review_evidence()`: đọc chữ (PDF, DOCX; ảnh và PDF scan dùng OCR), rồi chạy kiểm tra theo luật và tóm tắt | `src/services/evidence_review.py` (mới) |
| Kiểm tra theo luật: checklist từ khóa theo loại minh chứng (khớp cả không dấu); file trùng hệt với hồ sơ SV khác (sha256, không nêu tên SV đó) hoặc với mốc khác của chính SV; file gần như không có chữ; không thấy nội dung đặc trưng của loại đã khai; giấy tờ doanh nghiệp không có tên doanh nghiệp đã đăng ký; chuẩn đầu ra chưa nhắc tới (cho báo cáo) | `evidence_review.py`, `config/cohort.yaml` (`evidence_review`) |
| Tóm tắt bằng LLM (`classify`, văn bản đã che PII, tối đa 6.000 ký tự). Prompt tách riêng, viết ở ngôi thứ ba, không khuyến nghị duyệt | `prompts/evidence_review.md` (mới) |
| `GET /evidence/{id}/review`: **chỉ GV/QTV**, cùng phạm vi truy cập hồ sơ. Tính ở lần đầu rồi lưu vào `Evidence.ai_review` (file không đổi sau khi nộp) | `progress_routes.py`, `src/models/orm.py` |
| Cột mới `evidence.ai_review` (JSON). `init_db` tự `ALTER TABLE` cho DB đã có; `_ADDED_COLUMNS` được mở rộng để dùng cho nhiều bảng | `src/db.py` |
| Panel "Gợi ý AI đọc minh chứng" bên phải cửa sổ xem file (trên điện thoại nằm dưới, gập được): tóm tắt, cảnh báo, checklist ✓/?, căn cứ, chuẩn đầu ra, giới hạn. SV mở file của mình **không** thấy panel | `EvidencePreview.jsx`, `styles/components.css` |

## Cách kiểm tra

- `pytest tests/`: **202 passed**, ruff sạch. File mới `tests/test_vin15/test_evidence_review.py` kiểm tra:
  - checklist và tóm tắt ở chế độ không LLM;
  - **văn bản gửi tới LLM không chứa** tên SV, MSSV, email, tên doanh nghiệp, mã số thuế;
  - cảnh báo file trùng giữa hai SV, file ít chữ, thiếu tên doanh nghiệp;
  - endpoint chỉ cho GV phụ trách, lần gọi thứ hai lấy từ cache;
  - khi lỗi thì trả `unavailable` và không lưu cache.
- Trình duyệt (`tests/ui/queue-preview-check.mjs`, fixture `tests/ui/fixtures/bao-cao-cuoi-ky-mau.docx`): **47/47 PASS**, chạy với **OpenAI thật (gpt-4o-mini)**:
  - sv04 nộp báo cáo Word qua giao diện. SV mở file thì không có panel AI.
  - gv01 mở file: thấy tóm tắt chính xác, checklist ✓ ở 3 mục và "?" ở "Bài học kinh nghiệm" (file không có phần này), kèm câu giới hạn về chữ ký.
  - gv01 mở `hand_calc.jpg` (khai là "phiếu đánh giá DN" nhưng là ảnh bài tính tay): OCR đọc được 41 ký tự, có 3 cảnh báo (ít chữ, không đúng loại, không có tên doanh nghiệp). Model tóm tắt: "Tài liệu không giống loại minh chứng Phiếu đánh giá…".
- Lỗi phát hiện qua ảnh chụp và đã sửa:
  - model xưng "bạn" → sửa prompt;
  - dòng căn cứ dính liền vào đoạn giới hạn → tách thành dòng riêng;
  - trên điện thoại các cảnh báo mất dấu đầu dòng → thêm `list-style` rõ ràng.

## Chưa kiểm tra / lưu ý

- **File dùng chung đã sửa** (cần reviewer nhóm khác): `src/models/orm.py` (thêm cột), `src/db.py` (`_ADDED_COLUMNS` cho nhiều bảng).
- **Chi phí và độ trễ:** mỗi file gọi LLM một lần, ở lần đầu GV mở; sau đó lấy từ cache. Ảnh và PDF scan phải chạy OCR nên lần đầu có thể mất vài giây đến vài chục giây; panel tải sau file nên không chặn việc xem. Chưa đo p95.
- **Cache không tự làm mới** khi đổi prompt hoặc checklist. Muốn tính lại thì chạy `UPDATE evidence SET ai_review = NULL`. DB dev đã được xóa cache một lần sau khi sửa prompt; các bản cache đó đều do lần test tạo ra.
- **Checklist dò bằng từ khóa** nên có thể sót (báo cáo diễn đạt khác) hoặc nhận nhầm. Vì thế mục chưa thấy được đánh "?" chứ không đánh ✗.
- **Chưa có bộ eval chất lượng tóm tắt** trên minh chứng thật (cách làm giống `eval/` của nhóm 3).
- **Script e2e ghi dữ liệu thật:** mỗi lần chạy, sv04 upload thêm 1 PDF và 1 DOCX, và có thể gọi LLM vài lần.
