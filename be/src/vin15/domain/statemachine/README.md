# State machine

Cổng **duy nhất** để đổi trạng thái là `StateMachine.transition(source, target, actor, subject, reason)` (`machine.py`);
bảng cạnh của từng thực thể ở `definitions.py` (theo `docs/nghiep-vu-thuc-tap.md` mục 6).

- Cạnh quyết định chỉ đi được khi `actor.kind == human`, đúng vai trò **và** đúng phạm vi (`Subject`: chủ hồ sơ, GV phụ trách; QTV toàn bộ).
- `agent` luôn bị `PermissionDeniedError`; `system` chỉ đi cạnh khai báo `system=True` (đánh dấu mốc quá hạn) (BR-S1).
- Cạnh `needs_reason`: thiếu lý do thì `ReasonRequiredError` (BR-S2).
- `StateMachine.audit(...)` trả `AuditEntry` để service ghi cùng transaction với thay đổi dữ liệu (BR-S3).
