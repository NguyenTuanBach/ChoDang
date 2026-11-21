# Nhóm 3 — nền tảng bảo mật và policy assistant

## Đã thực hiện

- Thêm kiểm tra cấu hình: production không được chạy với `dev-only-change-me` và yêu cầu `JWT_SECRET` tối thiểu 32 ký tự.
- JWT có `jti` ngẫu nhiên và hỗ trợ thu hồi trong process.
- Thêm `POST /api/v1/auth/logout` để thu hồi Bearer token hiện tại.
- Bổ sung các mẫu prompt injection tiếng Việt không dấu cho policy guard.
- Thêm regression tests cho JWT revoke, production secret và prompt injection.

## Giới hạn còn lại

- Danh sách token thu hồi hiện lưu trong memory; khi chạy nhiều worker cần chuyển sang Redis/DB dùng chung.
- OIDC hiện lấy danh tính từ `userinfo`; cần bổ sung xác minh chữ ký `id_token` khi bật provider thực tế.
