# Kế hoạch test các agent ngoài chat

Phạm vi: ba agent một-lượt, không có công cụ ghi: **Chuẩn hóa hồ sơ** (`intake`), **Giám sát** (`monitor`), **Tiền thẩm** (`pre_review`).
Trợ lý chính sách (chat) có kế hoạch riêng ở `docs/thiet-ke-agent-hoi-dap.md`.

Trạng thái hiện tại (2026-11-21): code và nối FE đã có; chỉ **Tiền thẩm** đã chạy thật (LLM thật, đề cương, đạt). Chưa agent nào có test tự động.

## Nguyên tắc
- Agent chỉ trả kết luận có cấu trúc; **BE kiểm và ghi**. Test phải kiểm cả hai phía: agent trả đúng, BE không tin mù quáng.
- Bất biến cần chứng minh: agent không đổi trạng thái nào (số lần = 0); PII không rời hệ thống; thiếu LLM thì hệ thống vẫn chạy (X5).
- Hai tầng: (A) smoke thủ công với LLM thật, một lần, để biết chạy được; (B) test tự động với LLM giả, để khóa hành vi.

## Việc chuẩn bị
1. PDF có chữ giả lập giấy tiếp nhận (có tên DN, MST, địa chỉ, người hướng dẫn, email, SĐT, ngày); thêm 1 PDF quét (không lớp chữ), 1 PNG, 1 PDF hỏng.
2. Hồ sơ `in_progress` có đề cương đã duyệt + chuẩn đầu ra khóa + nhật ký (hồ sơ SV B có 11 nhật ký; cần kỳ thực tập đã bắt đầu).
3. Chạy `MonitoringService.scan()` bằng script (không có nút kích hoạt; job chỉ chạy hằng ngày/theo sự kiện). Không thêm endpoint nếu chưa cần.

## A. Chuẩn hóa hồ sơ (`intake`)
Kích hoạt: SV bấm "gợi ý" trên giấy tiếp nhận → `POST /api/student/internship/documents/{id}/extract`.

| # | Ca | Kỳ vọng |
|---|---|---|
| I1 | PDF có chữ, đủ trường | Trả gợi ý đúng giá trị, kèm `confidence` và `source`; MST/email/SĐT được **khôi phục** giá trị thật (không còn nhãn `[EMAIL_1]`) |
| I2 | PDF thiếu một số trường | Chỉ trả trường có trong văn bản; không bịa |
| I3 | PII không rời hệ thống | Bắt payload gửi LLM (test tự động, LLM giả): không chứa email/SĐT/MST/mã SV gốc |
| I4 | PNG/JPG | Không gửi LLM; trả ghi chú "nhập tay" |
| I5 | PDF quét (không lớp chữ) / PDF hỏng | Ghi chú "nhập tay", không lỗi 5xx |
| I6 | Văn bản chứa lệnh ("bỏ qua hướng dẫn...") | Bị bỏ qua (văn bản là dữ liệu) |
| I7 | LLM trả JSON hỏng / agent tắt | Trả `fields` rỗng + ghi chú; form vẫn nhập tay được |
| I8 | Phân quyền | SV khác không extract được giấy của người khác (403/404) |
| I9 | Gợi ý không tự ghi | Sau extract, hồ sơ chưa đổi cho tới khi SV xác nhận và lưu |

## B. Giám sát (`monitor`)
Kích hoạt: `scan()` (luật tất định + `/v1/monitor/review` cho phần cần LLM). Chỉ hồ sơ `in_progress` mới gọi LLM.

| # | Ca | Kỳ vọng |
|---|---|---|
| M1 | Hồ sơ có mốc quá hạn / thiếu nhật ký / thiếu minh chứng | Cờ theo luật được tạo (`created_by=system`), GV phụ trách nhận thông báo |
| M2 | Nhật ký lệch chuẩn đầu ra rõ ràng | Agent đề xuất `outcome_mismatch`; BE ghi cờ `created_by=agent`, audit `actor_kind=agent` |
| M3 | Nhật ký sơ sài/lặp nguyên văn | `weak_evidence` |
| M4 | Hồ sơ bình thường | Không có cờ nào |
| M5 | Quét lại khi chưa đổi gì | Không tạo cờ trùng (dấu vân tay) |
| M6 | GV bác cờ có lý do, quét lại | Không tái tạo cờ đã bác (C8) |
| M7 | Agent trả loại/mức ngoài danh sách (`critical`, `approve`...) | BE bỏ qua |
| M8 | Nhắc SV | Đúng mẫu cố định; ≤ 1 lần/ngày, ≤ 3 lần/(mốc, lý do); chỉ 07:00-21:00; lần thứ 3 leo thang thành cờ `reminder_escalation` |
| M9 | Agent tắt / timeout | `scan` vẫn xong, cờ theo luật vẫn có, thống kê `agent: unavailable` |
| M10 | Bất biến HITL | Sau scan, không hồ sơ/đề cương/mốc/ngoại lệ/tín chỉ nào đổi trạng thái (so snapshot trước/sau) |
| M11 | PII trong payload gửi agent | Đề cương/nhật ký đã che (kiểm payload ở test LLM giả) |
| M12 | Phạm vi cờ | GV chỉ thấy cờ SV mình phụ trách; SV không xem được cờ (403) |
| M13 | Email tổng hợp hằng ngày | `daily_digest` chỉ gửi cho GV có cờ mở hoặc việc chờ |

## C. Tiền thẩm (`pre_review`)
Đã đạt: đề cương, LLM thật. Cần thêm:

| # | Ca | Kỳ vọng |
|---|---|---|
| P1 | Đề cương (đã đạt) | Có `summary`, `outcome_matches`, `concerns` |
| P2 | Hồ sơ cuối kỳ (`subject_kind` khác) | Tóm tắt + `evidence_notes`; chạy được |
| P3 | Agent trả mã chuẩn đầu ra không có trong khóa | BE/agent lọc bỏ |
| P4 | Độ dài | Cắt đúng giới hạn (`summary` 1500, `concerns` 8...) |
| P5 | Phân quyền | SV gọi → 403; GV không phụ trách → bị từ chối |
| P6 | Không quyết thay GV | Sau pre-review trạng thái đề cương/hồ sơ không đổi |
| P7 | Agent tắt | Lỗi rõ ràng (503/timeout), không treo trang |

## Thứ tự thực hiện
1. **Smoke thật** (một lệnh gộp, in từng bước): I1, I2, I4, I5 → M1-M5, M8 (qua `scan()`), M10 → P2. Ghi lỗi tìm được.
2. Sửa lỗi phát hiện.
3. **Test tự động** (LLM giả, `agent/tests/` và `be/tests/`): I3, I6, I7, M7, M9, M11, P3, P4 ở agent; I8, I9, M5, M6, M10, M12, P5, P6 ở BE. Mỗi agent một file test, theo mẫu `test_policy_assistant.py`.
4. Cập nhật `docs/changes/` và mục "Trạng thái hiện tại" trong `CLAUDE.md`.

## Rủi ro đã biết
- Họ tên tự do không che được bằng regex (R2): I3 chỉ kiểm email/SĐT/MST/mã SV.
- Chất lượng đánh giá của LLM (M2, M3, I1) phụ thuộc mô hình; coi là smoke, không khẳng định chắc chắn; nên chạy 2-3 lần.
- Dữ liệu thử còn trong DB; `make seed-dev` để dọn.
