# State machine (chưa cài đặt)

Cổng **duy nhất** để đổi trạng thái là một hàm `transition(entity, from, to, actor, reason)`.
Quy tắc từ `docs/nghiep-vu-thuc-tap.md` mục 6:

- Cạnh quyết định (xác nhận hồ sơ, duyệt đề cương, chấp nhận mốc, duyệt ngoại lệ, thẩm định/phê duyệt tín chỉ)
  chỉ đi được khi `actor.kind == human`, đúng vai trò **và** đúng phạm vi (GV phụ trách, QTV, SV chủ hồ sơ).
- `agent` và `system` gọi vào cạnh quyết định phải bị `PermissionDeniedError` (BR-S1).
- Từ chối, yêu cầu sửa, không duyệt: bắt buộc có lý do (BR-S2).
- Mỗi chuyển trạng thái ghi một dòng `audit_event` (BR-S3).

Thực thể cần máy trạng thái: hồ sơ thực tập, đề cương, mốc, gia hạn, ngoại lệ, cờ rủi ro, công nhận tín chỉ.
