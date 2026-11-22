# Hạn lời mời 3 giờ

## Mục tiêu
Lời mời tài khoản chỉ có hiệu lực 3 giờ; quá hạn thì không đăng nhập được và phải mời lại.

## Đã làm
- `domain/model/user.py`: `INVITATION_TTL = 3h`, trường `invited_at`, `User.invitation_expired()`.
- `user_repository.py`: đọc `invited_at` (cột đã có từ V1); `set_status` đặt lại `invited_at = now()` khi chuyển sang `invited` (mời lại).
- `account_activation_service.py`: lời mời quá hạn bị từ chối ở lần đăng nhập đầu (dùng chung cho đăng nhập dev và Google).
- `account_controller.py`: `/api/invitations` trả thêm `invited_at` và `invitation_expired`.
- Test: `tests/domain/test_invitation_expiry.py` (5 test, đạt).

## Chưa làm / lưu ý
- **Giao diện chưa làm**: thẻ đỏ "Từ chối" + nút "Mời lại" khi quá hạn, chỉ hiện "Thu hồi lời mời" khi còn hạn. FE mới có thẻ trạng thái xanh/vàng/đỏ theo `status`.
- Cần khởi động lại BE để áp dụng.
- `pytest` (bỏ e2e/integration): 230 đạt, 6 lỗi đều ở `tests/presentation/test_agent_tools.py` ("test này không dựng dịch vụ tín chỉ"), không liên quan thay đổi này nhưng chưa kiểm tra có sẵn từ trước hay không.
- BE còn trả thêm `reviewed_at` cho minh chứng (`case_repository.evidence_for_internship`) để FE hiện cột "Cập nhật".
