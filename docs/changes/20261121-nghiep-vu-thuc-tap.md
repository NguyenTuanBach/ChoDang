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
Smoke test thủ công đã làm một phần (xem mục kết quả bên dưới); các bước đầy đủ:
1. `make install` (có thêm `boto3`, `pypdf`), `make seed-dev`, `scripts/start.sh`; mở `http://localhost:3000`.
2. Đăng nhập dev: QTV `qtv@example.test` mời GV mới (email `@example.test`), GV mời SV, SV đăng nhập (kích hoạt lần đầu), khai hồ sơ → nộp → GV xác nhận → SV nộp đề cương → GV duyệt →
   nộp mốc kèm minh chứng → GV chấp nhận → SV nộp kết thúc → GV thẩm định → QTV phê duyệt → xem `/admin/lms` (việc đồng bộ) và `/student/grades`.
3. Dữ liệu có sẵn: SV A (đang thực tập, trễ M3), SV B (chờ thẩm định, nộp M5 rồi để GV chấp nhận M4/M5), SV C (chưa có hồ sơ, chưa đủ tiên quyết LMS).
4. Tự động: `make test`, `make lint`, `make db-up && make be-test-db`, `cd fe && npm test && npm run lint && npx tsc --noEmit`.

## Kết quả smoke test (2026-11-21, thủ công qua curl/WebSocket, BE + agent chạy thật)
- **Đạt**: `/health`, `/health/readiness`, agent `/health`; đăng nhập dev (body `{"email": ...}`); ~35 GET theo vai trò QTV/GV/SV đều 200 (dashboard, queue, flags, audit, policies, LMS, config, notifications, CSV);
  RBAC 403 đúng (SV vào `/admin/*`, `/dashboard`, `/invitations`; GV vào `/admin/*`; SV xem hồ sơ người khác).
- **Luồng ghi đạt**: QTV tạo SV/học phần/điểm LMS, gán mã SV + giảng viên; SV C lưu hồ sơ → nộp (validate thiếu MST/địa chỉ/GV đúng) → GV `confirm` → `confirmed` + thông báo; nhật ký tuần của SV A (201).
- **Trợ lý (WS `/api/assistant/ws`, LLM thật gpt-4o-mini)**: hỏi quy chế có trích dẫn đúng; hỏi tiến độ cá nhân gọi `get_my_*` và trả đúng số liệu; câu ngoài phạm vi và prompt injection bị từ chối (`refused`).
  Câu hỏi điều kiện tín chỉ trả lời hơi mỏng (chỉ 1 điều kiện) — nghi do chưa có embedding (tìm theo từ khóa) hoặc quy chế mẫu ít điều khoản.
- **Chưa thử**: `pre-review` (body bắt buộc, chưa rõ schema), upload/tải tệp (R2/cục bộ), đề cương → mốc → thẩm định → phê duyệt tín chỉ → `credit_sync_job`, mời tài khoản/Google OAuth/email,
  job nền (digest/nhắc nhở), FE (toàn bộ), `make test`/`make lint`/`tsc`.
- Dữ liệu thử còn trong DB: SV C có hồ sơ `confirmed` (id 3), mã `SV003`, học phần `CS101` + 1 điểm; hội thoại 5–8 của SV A. Chạy lại `make seed-dev` để sạch.

## Smoke test bằng API, đợt 2 (2026-11-21)
- **Đạt**: đề cương (nộp v1 → GV yêu cầu sửa, thiếu lý do bị 422 → nộp v2 → duyệt → M2 tự `accepted`), `pre-review` (LLM thật), phân quyền (SV duyệt bị 403),
  mốc M3–M5 (không minh chứng thì không nộp; GV trả lại bắt buộc lý do; nộp lại → chấp nhận), chuẩn đầu ra phải khai báo trong khóa,
  tín chỉ: GV không thẩm định "đạt" khi T1/T4 chưa đạt (422), QTV không phê duyệt khi chưa thẩm định (409).
- **Chưa kiểm**: đường thành công thẩm định đạt → QTV phê duyệt → `credit_sync_job` → LMS (dùng hồ sơ SV B, cần mã SV, LMS, T5/T6); nộp nhật ký (hồ sơ SV C bắt đầu 01/12 nên bị từ chối đúng).
- Dữ liệu thử thêm: chuẩn đầu ra LO1, LO2 của 2026-K1; SV C có đề cương v1 (cần sửa) và v2 (đã duyệt), M1–M5 đã chấp nhận, hồ sơ `pending_credit`.

## Smoke test agent ngoài chat (2026-11-21, theo `docs/ke-hoach-test-agent.md`)
- **Chuẩn hóa hồ sơ** (gọi thẳng `/v1/intake/extract`): I1, I2, I4, I5, I6 đạt (PDF đủ trường trích đúng 10/10, MST/email/SĐT khôi phục từ nhãn; PDF thiếu trường chỉ trả trường có; PNG và PDF hỏng trả ghi chú nhập tay; lệnh chèn trong PDF bị bỏ qua). Chưa kiểm qua BE (I8, I9: cả 3 SV mẫu đã nộp hồ sơ nên không tải thêm tệp được) và I3, I7.
- **Giám sát, phía agent** (`/v1/monitor/review`): lệch chuẩn → `outcome_mismatch`, sơ sài → `weak_evidence`, bình thường → rỗng, chèn lệnh → chỉ ra loại cờ hợp lệ (M2, M3, M4, M7 đạt).
- **Giám sát, `scan()` đầu-cuối** (script gọi `MonitoringService.scan`): cờ theo luật được tạo, quét lại không tạo cờ trùng (M5), trạng thái hồ sơ/mốc/đề cương/yêu cầu không đổi sau quét (M10), agent khả dụng. **Chưa kiểm**: cờ do agent tạo qua BE (`agent_flags = 0` vì SV A không có đề cương duyệt + nhật ký), nhắc nhở theo khung giờ và leo thang (M8: lần quét này gửi 0 nhắc vì đã chạm giới hạn/ngày).
- **Lưu ý phát hiện**: luật minh chứng sinh **một cờ cho mỗi minh chứng và mỗi lý do** (8 cờ cho hồ sơ SV C: "rất nhỏ" và "trùng nội dung" cho từng tệp). Dễ gây nhiễu cho GV (rủi ro R4); nên gộp theo hồ sơ.
- Chưa chạy: Tiền thẩm hồ sơ cuối kỳ (P2), P3–P7.

## Việc làm tiếp (theo thứ tự)
1. Smoke test nốt luồng còn lại ở trên (đề cương → mốc + minh chứng → thẩm định → phê duyệt tín chỉ → LMS sync) và `pre-review`; mở FE `/student`, `/lecturer`, `/admin` bằng từng vai trò.
2. Chạy `make test`, `make lint`, `cd fe && npm test && npx tsc --noEmit && npm run lint`; sửa lỗi (test cũ `LoginPanel` có thể cần chỉnh vì thêm `/api/auth/providers`).
3. Viết test cho phần mới (state machine, phân quyền theo phạm vi, validate nộp hồ sơ, credit checklist, tích hợp DB).
4. Embedding quy chế (`make seed-dev` khi agent gọi được OpenAI) rồi chạy `make agent-eval`; xem lại câu trả lời điều kiện tín chỉ.
5. Danh sách thu hồi token bền; adapter LMS thật khi biết hệ thống trường; quy chế thật (R1).

## Lưu ý còn lại
- Cần khóa do bạn cấp trong `.env` (không dán vào chat): `R2_*`, `SMTP_*`, `GOOGLE_*`. Không có thì lưu tệp cục bộ, email chỉ ghi log, nút Google bị tắt.
- A4 chỉ trích từ **PDF có chữ**; họ tên tự do không che được bằng regex (rủi ro R2). Ảnh/PDF quét phải nhập tay.
- `uv.lock` đã đổi cho `boto3`/`pypdf` (đã commit).
- Quy chế trong DB vẫn là **bản mẫu**. Trang FE quản trị quy định `/admin/policies` (`PoliciesPanel`: danh sách phiên bản, nạp văn bản, xem trước đoạn đã tách, xuất bản) đã viết, `tsc --noEmit` đạt, **chưa chạy thử trên trình duyệt** và chưa có test.
- Job nền chạy trong tiến trình BE (một instance); khóa advisory chống chạy đôi. Mốc chỉ M1–M5 (CHECK ở V4); muốn mốc tùy ý phải nới CHECK bằng migration mới.
- Chưa có chuyển "đổi người hướng dẫn tại doanh nghiệp" khi duyệt ngoại lệ: ngoại lệ được duyệt chỉ ghi quyết định (không tự sửa dữ liệu hồ sơ).
