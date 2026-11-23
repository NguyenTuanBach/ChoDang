# AI đọc giấy tờ để tự điền (giấy tiếp nhận + giấy xác nhận M5 + đính kèm trong Trợ lý)

Ngày: 2026-11-23 · Trạng thái: **BE + agent đã smoke test với LLM thật (2026-11-23)**; FE chưa mở trên trình duyệt; chưa có test tự động.

## Vấn đề / mục tiêu
- Trước đây AI chỉ gợi ý trường từ **giấy tiếp nhận dạng PDF có lớp chữ**; ảnh chụp/PDF scan bị chặn. Giấy xác nhận cuối kỳ (M5) chỉ lưu tệp.
- Đã chốt với người dùng: dữ liệu hiện là mock, AI sau này chạy nội bộ → **cho gửi ảnh/scan cho AI, không cần cờ cấu hình**.
- Mục tiêu: đọc được ảnh/scan; thêm trường cho giấy tiếp nhận; bộ trường cho giấy xác nhận/phiếu đánh giá M5 + đối chiếu với hồ sơ;
  hỏi "có muốn AI tự điền" ngay sau khi tải; đính kèm giấy trong ngăn Trợ lý → tự mở trang đúng và điền nháp.
- HITL giữ nguyên: AI chỉ gợi ý; SV bấm lưu/xác nhận; GV vẫn chấp nhận/trả lại mốc M5.

## Đã làm

### Agent
- `core/ai_client.py`: thêm khả năng `vision`; `chat(..., capability=...)` để chỉ dùng đường LLM có vision (proxy khai qua `AICLIENT_CAPABILITIES`).
- `core/structured.py`: `ask_json_parts` (nội dung người dùng gồm chữ + ảnh).
- `intake/agent.py` (viết lại): `kind` = `receipt_letter` | `completion_letter` | `auto` (LLM tự phân loại, trả `kind`).
  PDF có chữ → che PII như cũ; ảnh PNG/JPG → gửi thẳng; PDF quét → dựng tối đa 3 trang thành PNG (`pypdfium2` + `pillow`, thêm vào `pyproject.toml`).
  Hai bộ trường `RECEIPT_FIELDS`, `COMPLETION_FIELDS`.
- `prompts/intake.system.md`: dùng chung, có `{{doc_kind}}`; `runtime/http/structured_agents.py`: `IntakeRequest.kind`.

### Trường
- **Giấy tiếp nhận → hồ sơ**: 10 trường cũ + `mode`, `department`, `mentor_title`, số/ngày ký giấy, người ký + chức vụ
  (lưu ở `receipt_letter_number/date`, `receipt_signer_name/title`). `student_name`/`student_code` chỉ để cảnh báo nếu khác tài khoản.
- **Giấy xác nhận / phiếu đánh giá (M5)**: tên DN, MST, tên/mã SV, vị trí, phòng ban, ngày bắt đầu/kết thúc thực tế, người hướng dẫn,
  xếp loại, điểm, nhận xét, người ký + chức vụ, số/ngày văn bản, có dấu/chữ ký (gợi ý).

### BE
- Migration `V12__document_autofill.sql`: 6 cột mới ở `internship`; bảng `evidence_extraction` (bật RLS).
- `service/internship/intake_service.py`: `extract` (giấy tiếp nhận, kèm `warnings`), `extract_evidence` (M5), `auto_intake` (chat: AI phân loại →
  lưu vào `internship_document` hoặc minh chứng M5 → trả `kind`, `target_page`, id, `fields`).
- `service/milestone/evidence_check.py` (hàm thuần): đối chiếu tên DN, MST, tên/mã SV, người hướng dẫn, số tuần thực tế < đăng ký, thiếu dấu.
- `MilestoneService.own_evidence`, `confirm_evidence_fields` (lưu + audit `confirm_fields`).
- `InternshipService.upload_document`: chưa có hồ sơ thì tự tạo nháp rỗng.
- Endpoint: `POST /api/student/intake/auto`, `POST /api/student/evidence/{id}/extract`, `PUT /api/student/evidence/{id}/fields`.
  `evidence_for_internship` trả thêm `extraction`.

### FE
- `lib/autofill.ts`: kho gợi ý tạm (ngăn Trợ lý đặt → trang đích lấy một lần), `usePendingAutofill`, nhãn trường, lớp `PULSE` (nút nhấp nháy).
- `components/shared/AutofillPrompt.tsx`: dialog "Bạn có muốn AI tự điền không?" sau khi tải giấy.
- `InternshipForm.tsx`: thêm ô cho trường mới; tải giấy → hỏi → AI gợi ý (có "Dùng tất cả"); cảnh báo tên/mã SV; gợi ý từ chat điền thẳng vào form
  (chưa lưu), nút **Lưu bản nháp** nhấp nháy + cuộn tới. Thẻ giấy tiếp nhận hiện cả khi chưa có hồ sơ.
- `EvidenceFieldsForm.tsx` + `MilestonesPage.tsx`: ở M5, mỗi tệp có form "Thông tin trên giấy" (AI đọc → điền, độ tin cậy, nguồn) → **Xác nhận thông tin** → cảnh báo lệch.
- Ngăn Trợ lý (`Composer` nút 📎, `AssistantProvider.attachDocument`, `AutofillCard.tsx`): chỉ SV; gọi thẳng BE (không qua LLM hội thoại/WS),
  hiện thẻ gợi ý, chuyển sang `/student/internship` hoặc `/student/milestones`, trang đó điền nháp và nút xác nhận nhấp nháy.
- `InternshipDetailView.tsx` (GV/QTV): hiện trường mới của hồ sơ; ở mốc M5 hiện bảng trường SV đã xác nhận + cảnh báo lệch.

## Cách kiểm tra
1. `make install` (cài `pypdfium2`, `pillow`), `scripts/start.sh`, `make seed-dev` (áp V12).
2. SV C (chưa có hồ sơ): mở ngăn Trợ lý → 📎 ảnh giấy tiếp nhận → thẻ gợi ý → tự sang trang Hồ sơ, form điền sẵn, nút Lưu nhấp nháy → Lưu.
   GV mở hồ sơ thấy "Các trường do AI gợi ý…".
3. Trang Hồ sơ: tải PDF scan → dialog → "Có, tự điền" → danh sách gợi ý.
4. SV B (đang thực tập): M5 tải ảnh giấy xác nhận có tên DN khác → dialog → điền → Xác nhận → cảnh báo; GV mở chi tiết hồ sơ thấy bảng + cảnh báo.
5. Khi được yêu cầu: `make test`, `make lint`, `tsc`.

## Kết quả smoke test BE (2026-11-23, LLM thật, giấy mẫu tự dựng)
- `intake/auto` + ảnh PNG giấy tiếp nhận (SV mới `sv.f@example.test`, mã SV2026006): `kind=receipt_letter`, `target_page=internship`, đúng 17/17 trường,
  cảnh báo lệch tên/mã SV; tự tạo hồ sơ nháp rỗng (AI không ghi trường nào). ~30 s.
- Tải PDF scan → `documents/{id}/extract`: dựng ảnh bằng pypdfium2, đúng 17/17 trường. ~20 s.
- `intake/auto` + PDF có lớp chữ: đi đường che PII; MST/email/SĐT khôi phục đúng. ~18 s.
- `PUT /api/student/internship` lưu đủ 6 cột mới + `confirmations`; ngày sai định dạng → 422.
- `intake/auto` + ảnh JPG giấy xác nhận (SV A): `kind=completion_letter`, lưu minh chứng M5, 17 trường (đọc nhầm nhỏ: "Khác"→"Khắc", mất một số 9 trong mã SV).
- `PUT evidence/{id}/fields`: bắt lệch tên SV và "thực tế ~5 tuần < đăng ký 11 tuần"; GV xem `/api/internships/{id}` thấy `extraction`.
- Chặn đúng: SV khác đọc/xác nhận giấy không phải của mình → 404; GV gọi endpoint SV → 403; `.txt` → 400; trường lạ bị bỏ; giá trị xác nhận sai → 422;
  hồ sơ đã nộp mà đính kèm giấy tiếp nhận → 409.
- Lưu ý từ test: (1) `intake/auto` gọi AI **trước** khi biết có được lưu không → hồ sơ đã nộp vẫn chờ ~20 s rồi mới báo 409;
  (2) model trả confidence gần như luôn 0.9 nên nhãn "cần kiểm" ít khi hiện; (3) giấy xác nhận qua chat chưa báo lệch ngay, chỉ báo sau khi SV bấm Xác nhận.
- Dữ liệu test còn trên DB chung: tài khoản `sv.f@example.test` (hồ sơ nháp, 3 giấy tiếp nhận), minh chứng M5 id 10 của SV A (kèm `evidence_extraction`).

## Chưa kiểm tra / lưu ý
- Chưa chạy trên trình duyệt; chưa có test tự động cho phần mới
  (nên thêm: `evidence_check`, `IntakeExtractor` chọn đường chữ/ảnh với AiClient giả, `auto_intake`).
- Ảnh/scan **không che PII** (đã chốt). PDF có chữ vẫn che email/SĐT/MST.
- Đính kèm trong chat cho giấy xác nhận cần hồ sơ đang thực tập (M5 tồn tại); nếu không, BE báo lỗi trên thẻ.
- `ruff format` báo nhiều file (kể cả code cũ) chưa theo format; chưa format lại để khỏi đổi diff lớn.
