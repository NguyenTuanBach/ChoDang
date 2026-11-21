# Nghiệp vụ thực tập cho ba vai trò (SV / GV / QTV) + LMS mini

## Mục tiêu
Trước đó chỉ có khung, Trợ lý chính sách và đăng nhập dev; **chưa có nghiệp vụ nào ghi dữ liệu**. Đợt này làm hết nhóm A, C, D, X của
`docs/nghiep-vu-thuc-tap.md` theo lát dọc (migration → repository → state machine → service → controller → FE), kèm Google OAuth và LMS mini.

## Đã làm
- **Nền (X)**
  - `domain/statemachine/` (`machine.py`, `definitions.py`): cổng duy nhất `StateMachine.transition(source, target, actor, subject, reason)`;
    bảng cạnh cho hồ sơ, đề cương, mốc, gia hạn/ngoại lệ (hai máy: GV duyệt / QTV duyệt), cờ rủi ro, thẩm định tín chỉ. BR-S1 (agent luôn bị từ chối, `system` chỉ đi cạnh `system=True`),
    BR-S2 (cạnh `needs_reason`), BR-S3 (`StateMachine.audit` trả `AuditEntry`, repository ghi **cùng transaction**).
  - `domain/authorization.py` + `presentation/controller/dependencies.py` (`require_role`, `student_user`, `lecturer_user`, `admin_user`, `staff_user`); lỗi mới `ScopeDeniedError`, `ReasonRequiredError`.
  - Cổng `domain/ports.py` (`FileStorage`, `Mailer`) + adapter: `infrastructure/storage` (Cloudflare R2 qua `boto3`, hoặc đĩa cục bộ `.data/files`), `infrastructure/mail` (SMTP Gmail, hoặc chỉ ghi log).
    Chọn adapter theo cấu hình (`R2_*` đủ thì dùng R2; `SMTP_USER`/`SMTP_PASSWORD` có thì dùng SMTP).
  - Thông báo trong ứng dụng + hộp thư email đi có thử lại (`service/notification`, bảng `notification`, `email_outbox`).
  - Job nền (`service/jobs/scheduler.py`, chạy trong `lifespan`): khóa advisory Postgres, đánh dấu mốc quá hạn, gửi email, đồng bộ LMS, giám sát + email tổng hợp hằng ngày (giờ `DAILY_DIGEST_HOUR`).
- **Tài khoản và mời (A1, A2, D14)**: `service/user/account_service.py` (QTV mời GV, GV mời SV; thu hồi, mời lại, gán GV phụ trách, mã sinh viên), bootstrap QTV từ `APP_ADMIN_EMAILS` lúc khởi động,
  `AccountActivationService` (kích hoạt lần đăng nhập đầu, dùng chung cho dev-login và Google), Google OAuth (`infrastructure/oauth`, `/api/auth/google/*`, `/api/auth/providers`).
- **Hồ sơ (A3–A6)**: `InternshipService` (nháp, tải giấy tiếp nhận, kiểm trước khi nộp có trích dẫn điều khoản đang hiệu lực, phát hiện MST trùng, nộp có chụp phiên bản BR-S4, GV xác nhận/yêu cầu sửa/từ chối).
  Xác nhận sinh mốc từ mẫu của QTV (M1 tự đạt). **AI trích trường (A4)**: `IntakeService` → agent `/v1/intake/extract`; chỉ PDF có chữ, che PII rồi khôi phục nhãn cục bộ; SV xác nhận từng trường (`field_confirmations`).
- **Đề cương, mốc, nhật ký, minh chứng (A7–A13)**: `OutlineService` (phiên bản, đối chiếu chuẩn đầu ra; duyệt ⇒ hồ sơ `in_progress` + M2 đạt trong một transaction),
  `MilestoneService` (nộp mốc cần minh chứng với M3–M5, GV chấp nhận/trả lại, nhật ký tuần, nhận xét), `service/files/upload.py` (kiểm loại tệp bằng chữ ký byte, không tin đuôi/Content-Type).
  `ReportService`: danh sách có lọc + CSV, hàng chờ xếp theo ưu tiên, chi tiết hồ sơ.
- **Gia hạn, ngoại lệ, tín chỉ (D1–D4)**: `RequestService` (người duyệt theo `affects_credit` của loại ngoại lệ, D13; gia hạn được duyệt ⇒ cập nhật hạn mốc),
  `CreditDecisionService` (SV nộp kết thúc → GV thẩm định bảng T1–T6, chỉ "đạt" khi mọi điều kiện đạt → QTV phê duyệt cuối; phê duyệt tạo `credit_sync_job` **cùng transaction**).
- **LMS mini (D5, D6)**: bảng `lms_*` chỉ `infrastructure/lms` được đụng; `LmsPort` (`prerequisite_status`, `student_record`, `post_credit_result`) là cửa duy nhất của nghiệp vụ; sinh viên khớp bằng **mã sinh viên**;
  `LMS_ADAPTER=mini`. Giao diện quản trị (học phần, tiên quyết, điểm, CSV) và SV xem bảng điểm. `LmsSyncService`: gửi, thử lại có backoff, báo QTV khi thất bại hẳn.
- **Dashboard (D7, D8)**: tiến độ, tỷ lệ trễ hạn, cờ, thời gian ra quyết định (trung vị), kết quả công nhận, đồng bộ LMS; xuất CSV; trang audit cho QTV.
- **Giám sát và tiền thẩm (C1–C8)**: `service/monitoring/detector.py` (luật tất định: quá hạn, thiếu nhật ký ≥2 tuần, thiếu điều kiện tín chỉ ≤14 ngày, minh chứng trùng/rỗng) nên vẫn chạy khi LLM sập;
  `MonitoringService` (tạo cờ, nhắc theo mẫu cố định, chống spam ≤1 lần/ngày, ≤3 lần/(mốc, lý do), 07:00–21:00, lần 3 leo thang thành cờ; cờ unique theo dấu vân tay nên không lặp và không tái tạo cờ đã bác);
  `PreReviewService`. Agent mới ở `agent/`: `intake/`, `monitor/`, `pre_review/`, `core/structured.py`, `runtime/http/structured_agents.py`, 3 prompt `.md`.
- **FE**: `AuthGate roles`, menu theo vai trò, ~40 file trang/thành phần (xem `fe/README.md`).
- Migration `V5`–`V10`; seed dev mở rộng (mã SV, chuẩn đầu ra, đề cương, nhật ký có nội dung, LMS mẫu: SV C chưa đủ tiên quyết).

## Khác với kế hoạch
- **Agent không có công cụ ghi** (kế hoạch ban đầu định nới `read_only` cho `create_flag`/`send_reminder`). Thay vào đó BE gửi dữ liệu đã che PII, agent trả kết luận cấu trúc, BE tự kiểm loại cờ
  (`AGENT_FLAG_KINDS`) rồi tự ghi. Giữ nguyên bất biến `read_only` của registry công cụ và HITL mạnh hơn. Nhắc nhở/cờ luật tất định do BE tạo (`actor_kind=system`).
- Danh sách thu hồi token vẫn nằm trong RAM (chưa chuyển vào DB).

## Cách kiểm tra
Tôi **chưa chạy bất kỳ test hay server nào** (theo yêu cầu): chỉ kiểm cú pháp Python bằng `ast.parse`. Để smoke test:
1. `make install` (có thêm `boto3`, `pypdf`), `make seed-dev`, `scripts/start.sh`; mở `http://localhost:3000`.
2. Đăng nhập dev: QTV `qtv@example.test` mời GV mới (email `@example.test`), GV mời SV, SV đăng nhập (kích hoạt lần đầu), khai hồ sơ → nộp → GV xác nhận → SV nộp đề cương → GV duyệt →
   nộp mốc kèm minh chứng → GV chấp nhận → SV nộp kết thúc → GV thẩm định → QTV phê duyệt → xem `/admin/lms` (việc đồng bộ) và `/student/grades`.
3. Dữ liệu có sẵn: SV A (đang thực tập, trễ M3), SV B (chờ thẩm định, nộp M5 rồi để GV chấp nhận M4/M5), SV C (chưa có hồ sơ, chưa đủ tiên quyết LMS).
4. Tự động: `make test`, `make lint`, `make db-up && make be-test-db`, `cd fe && npm test && npm run lint && npx tsc --noEmit`.

## Chưa kiểm tra / lưu ý
- **Toàn bộ code mới chưa được chạy**: nhiều khả năng còn lỗi nhỏ (SQL, kiểu TypeScript, import). Test BE/agent/FE cũ có thể cần chỉnh (đã sửa tay: `FakeLmsAdapter`/`LmsPort`, `["agents"]` ở agent, `DATA_TABLES`).
  Chưa viết test cho code mới.
- Cần khóa do bạn cấp trong `.env` (không dán vào chat): `R2_*`, `SMTP_*`, `GOOGLE_*`. Không có thì lưu tệp cục bộ, email chỉ ghi log, nút Google bị tắt.
- A4 chỉ trích từ **PDF có chữ**; họ tên tự do không che được bằng regex (rủi ro R2). Ảnh/PDF quét phải nhập tay.
- `uv.lock` chưa cập nhật cho `boto3`/`pypdf` (`uv sync` sẽ cập nhật). Các test cũ `LoginPanel` có thể cần chỉnh vì có thêm một lời gọi `/api/auth/providers`.
- Quy chế trong DB vẫn là **bản mẫu**; embedding quy chế cần chạy lại `make seed-dev` khi agent gọi được OpenAI. Chưa có trang FE quản trị văn bản quy định (API `/api/admin/policies` đã có).
- Job nền chạy trong tiến trình BE (một instance); khóa advisory chống chạy đôi. Mốc chỉ M1–M5 (CHECK ở V4); muốn mốc tùy ý phải nới CHECK bằng migration mới.
- Chưa có chuyển "đổi người hướng dẫn tại doanh nghiệp" khi duyệt ngoại lệ: ngoại lệ được duyệt chỉ ghi quyết định (không tự sửa dữ liệu hồ sơ).
