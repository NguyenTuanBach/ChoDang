# Đăng nhập dev (nhiều role)

## Mục tiêu
Bản dev chưa có đăng nhập Google, BE luôn đóng vai `AGENT_DEV_DEFAULT_USER_EMAIL`. Cần nút "Đăng nhập dev" để vào một tài khoản mẫu
(QTV, GV, SV) trên dữ liệu seed, và phát cùng loại phiên mà đăng nhập Google sẽ phát sau này.

## Đã làm
- **BE**
  - `service/auth/dev_login_service.py`: chỉ nhận email `@example.test` đang `active`; ghi `audit_event` (`session`/`dev_login`); phát token qua `ActorTokenService`.
  - `presentation/controller/auth_controller.py`: `GET /api/auth/me`, `POST /api/auth/logout` (luôn có); `GET /api/auth/dev-accounts`, `POST /api/auth/dev-login`
    (`dev_router`, chỉ được include khi `Settings.dev_login_enabled`, tức không phải production → ở production là 404).
  - Phiên là cookie `session` HttpOnly, `SameSite=Lax`; `current_user` đọc Bearer rồi cookie. `CurrentUserService` **không còn** rơi về người dùng mặc định
    (`AGENT_DEV_DEFAULT_USER_EMAIL` chỉ còn dùng ở `AgentSubjectResolver`, tức tool agent).
  - `UserRepository.list_by_email_suffix`.
- **FE**: `/login` (`LoginPanel`), `AuthGate` bọc trang chủ và `/assistant` (chưa đăng nhập → `/login`, thanh tên · vai trò · Đăng xuất), `lib/auth.ts`.
- **Test**: BE `tests/presentation/test_auth.py`; test cũ của trợ lý chuyển sang `session_client` (cookie) trong `tests/conftest.py`; e2e đăng nhập bằng dev-login.
  FE `AuthGate.test.tsx`, `LoginPanel.test.tsx`, `lib/auth.test.ts`.

## Cách kiểm tra
`make seed-dev` → `scripts/start.sh` → mở `localhost:3000`, bị đưa tới `/login`, chọn từng role. Đã curl thử BE và qua proxy của FE: đăng nhập, `/me`, đổi role,
từ chối email ngoài `@example.test`, logout thu hồi token. `vitest`, `eslint`, `tsc` của FE qua.

## Chưa kiểm tra / lưu ý
- **`pytest` của BE chưa chạy** sau thay đổi này (gồm test mới và các test cũ đã sửa sang cookie, cả e2e).
- Giao diện chưa xem trên trình duyệt thật; trang chat bị trừ chiều cao thanh trên (`--auth-bar-height`).
- Danh sách thu hồi token nằm trong RAM của tiến trình BE (restart thì token đã logout dùng lại được đến khi hết hạn 8 giờ).
- Chưa làm: đăng nhập Google, mời tài khoản (A1/A2), phân quyền theo role/phạm vi cho API nghiệp vụ.
