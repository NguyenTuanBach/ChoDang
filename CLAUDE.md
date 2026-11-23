# CLAUDE.md — Project context cho Claude Code

## Quick Rehydrate (≤ 60s)

Đọc nhanh khi mất context:
- **Đây là**: VIN-15 — hệ thống hỗ trợ thực tập bằng AI cho một trường (sản phẩm thật, đang làm lại nghiệp vụ từ đầu trên nhánh `konan`).
- **Đề tài**: `docs/problem-statement.md` (không đổi). Nghiệp vụ đã phân tích: `docs/nghiep-vu-thuc-tap.md` (bản nháp 0.1, có mã BR-*, A*, P*).
- **Cấu trúc**: `be/` (FastAPI, cổng 8000, gói `vin15`) + `agent/` (service AI riêng, cổng 8100, gói `vin15_agent`) + `fe/` (Next.js, cổng 3000). Đọc `be/README.md`, `agent/README.md`, `fe/README.md`.
- **Stack**: Python 3.12, uv, FastAPI, Pydantic v2, Postgres (Supabase) qua psycopg, migration SQL kiểu Flyway, SDK `openai`; FE Next.js (App Router, TypeScript, Tailwind CSS v4).
- **Chạy** (không cần Docker): `scripts/start.sh` (BE + agent + FE cùng lúc, Ctrl+C dừng tất cả), hoặc riêng lẻ `make install`, `make be-run`, `make agent-run`, `make fe-run`. Test: `make test`. Lint: `make lint`.
  Gọi thử LLM thật: `make agent-llm-check`.
- **Cấu hình**: `.env` ở gốc repo (mẫu `.env.example`), cả `be/` và `agent/` cùng đọc. BE không giữ khóa LLM, chỉ agent dùng.
- **Lịch sử thay đổi**: `docs/changes/` (đọc file mới nhất để biết việc vừa làm và phần còn dở).

## Trạng thái hiện tại (cập nhật khi đổi)

Có **khung** và **một tính năng đầu tiên: Trợ lý chính sách** (kế hoạch và tiến độ P0–P4 ở `docs/thiet-ke-agent-hoi-dap.md` mục 10):
- **Có**: khung BE/agent (`Database` + `SqlMigrator`, token HS256, lỗi, rate limit, `AiClient`); migration `V1`–`V4` (người dùng, audit, kho quy định,
  hội thoại, hồ sơ thực tập tối thiểu; RLS); BE: kho quy định (nạp/xuất bản/tìm kiếm lai), `/api/agent-tools/*`, chat WebSocket `/api/assistant/ws`,
  seed dev (`make seed-dev`); agent: vòng lặp tool, `search_policy`/`get_policy_clause`/`get_my_*`, che PII, trích dẫn, chế độ suy giảm,
  bộ eval (`make agent-eval`); FE `fe/`: trang kiểm tra kết nối và chat `/assistant`.
- **Có thêm**: đăng nhập dev (`/login` → nút "Đăng nhập dev", `POST /api/auth/dev-login`, cookie phiên HttpOnly; chỉ ngoài production), `GET /api/auth/me`, `POST /api/auth/logout`.
- **Có thêm (nghiệp vụ thực tập, xem `docs/changes/20261121-nghiep-vu-thuc-tap.md`)**: state machine (`domain/statemachine`), phân quyền theo vai trò và phạm vi,
  mời tài khoản + Google OAuth, hồ sơ (AI gợi ý trường), đề cương, mốc/nhật ký/minh chứng (R2), gia hạn/ngoại lệ, thẩm định → phê duyệt tín chỉ, **LMS mini** (`infrastructure/lms`, sau `LmsPort`),
  dashboard + CSV + audit, thông báo + email, job nền, giám sát + tiền thẩm (agent một-lượt không công cụ ghi), FE theo vai trò (`/student`, `/lecturer`, `/admin`). Migration `V5`–`V10` (V12: tự điền giấy tờ; V11 `journal_standup` đã áp trên DB chung nhưng không có file ở nhánh này).
- **Đã smoke test thủ công (2026-11-21)**: BE + agent chạy được; GET theo vai trò, RBAC, luồng hồ sơ draft→submitted→confirmed, chat Trợ lý (LLM thật) đều đạt.
  **Chưa**: đề cương → mốc → thẩm định → tín chỉ → LMS sync, `pre-review`, upload tệp, mời/OAuth/email, job nền, FE; **chưa có test tự động cho phần mới** và `pytest`/`vitest`/lint chưa chạy. Chi tiết ở `docs/changes/20261121-nghiep-vu-thuc-tap.md`.
- **Có thêm**: giao diện Tailwind (khung menu, đăng nhập, Tổng quan sinh viên có thanh hành trình, hàng chờ GV/QTV dạng thẻ; thiết kế ở `docs/thiet-ke-screen-flow.md`, chưa làm wizard hồ sơ/duyệt hai cột/ngăn Trợ lý nổi).
- **Có thêm**: trang FE quản trị quy định `/admin/policies` (nạp → xem trước → xuất bản; chưa chạy thử trên trình duyệt).
- **Có thêm (chưa chạy thử, xem `docs/changes/20261122-tro-ly-theo-vai-tro.md`)**: Trợ lý tách theo vai trò: prompt + văn phong riêng cho SV/GV/QTV (`agent/prompts/persona.*.md`), tool dữ liệu `staff/*` cho GV/QTV (BE kiểm phạm vi).
- **Có thêm (chưa mở trên trình duyệt, xem `docs/changes/20261122-ui-lms-va-side-chat.md`)**: UI kiểu LMS bằng shadcn/ui (sidebar + thanh trên, route group `fe/src/app/(app)`, `AuthProvider` + `RoleGuard`), ngăn Trợ lý nổi dùng chung một phiên chat qua các trang (`AssistantProvider`/`AssistantDock`, `Ctrl+J`), tool `navigate_to` để điều hướng bằng lời (`policy_assistant/pages.json` ↔ `fe/src/lib/nav.ts`), trang chủ 3 vai trò.
- **Có thêm (chưa chạy test, xem `docs/changes/20261123-tro-ly-dieu-huong-nang-cao.md`)**: Trợ lý biết trang đang mở (`ask.page` → `start.current_page`),
  mở được trang chi tiết hồ sơ (`internship_detail` + `internship_id` lấy từ `list_internships(student=…)`) và mở trang kèm bộ lọc (`filters` → query string; hàng chờ, hồ sơ, cờ rủi ro).
- **Có thêm (chưa chạy test, xem `docs/changes/20261123-tai-tep-quy-che-va-embedding.md`)**: `/admin/policies` tải tệp quy chế (.md/.txt/.docx/.pdf có lớp chữ → điền ô nội dung để sửa rồi nạp),
  cột Embedding + nút "Tạo embedding" bù phần còn thiếu.
- **Có thêm (BE đã smoke test với LLM thật, FE chưa mở; xem `docs/changes/20261123-ai-doc-giay-to-tu-dien.md`)**: AI đọc giấy tờ để tự điền — cả ảnh chụp/PDF scan (model vision, **không cờ**, đã chốt):
  giấy tiếp nhận → form hồ sơ (thêm phòng ban, chức vụ người hướng dẫn, số/ngày/người ký giấy); giấy xác nhận/phiếu đánh giá M5 → trường + đối chiếu hồ sơ (`evidence_extraction`, V12);
  hỏi "có muốn AI tự điền" sau khi tải; nút 📎 trong ngăn Trợ lý (SV) → thẻ gợi ý → mở trang đúng, điền nháp, nút lưu/xác nhận nhấp nháy.
- **Chưa có**: danh sách thu hồi token bền (đang ở RAM), adapter LMS thật (Moodle...); quy chế trong DB là **bản mẫu**.
- **Còn dở**: embedding quy chế (chạy lại `make seed-dev` hoặc bấm "Tạo embedding" ở `/admin/policies` khi agent gọi được OpenAI); lượt hỏi cá nhân đôi khi không gọi `get_my_*`; chưa chạy eval LLM thật; tool `get_my_*` của Trợ lý chưa trả thêm trạng thái đề cương.
- **Thứ tự làm tiếp**: smoke test nốt luồng còn lại + FE → `make test`/lint/tsc và sửa lỗi → viết test cho phần mới → embedding quy chế + `make agent-eval` → LMS thật khi biết hệ thống của trường → quy chế thật (R1).

## Current Invariants (để không drift)

- **Source of truth kỹ thuật**: code trong `be/src/` và `agent/src/`. File `.md` (kể cả file này) chỉ là
  tóm tắt — khi mâu thuẫn, CODE WINS.
- **BE và agent chỉ nói chuyện qua HTTP** (`be/.../infrastructure/agent_api`, kèm service token). BE không import
  `vin15_agent`, agent không import `vin15`. Hai test `test_architecture.py` kiểm điều này.
- **Hướng phụ thuộc trong BE**: `presentation → service → domain`, `infrastructure → domain`, `presentation` đi qua `Container`.
- **FE gọi BE chỉ qua HTTP**: trình duyệt gọi `/api/...` cùng origin, Next `rewrites` (`fe/next.config.ts`) chuyển sang BE; FE không gọi agent trực tiếp (agent chỉ BE gọi, cần service token).
- **Hướng phụ thuộc trong agent**: `runtime → <agent> → core → shared`. SDK `openai` chỉ được import trong `agent/src/vin15_agent/core/` (có test kiểm).
- **LLM**: mọi lời gọi đi qua `AiClient` (`core/ai_client.py`). Đường chính là OpenAI trực tiếp (`OPENAI_*`); proxy `AiClient`
  (`AICLIENT_*`) chỉ là dự phòng, chỉ dùng khi lỗi tạm thời (mất kết nối, timeout, 429, 5xx). Khóa là `SecretStr`, không log, không đưa vào prompt/commit.
- **Agent không có công cụ quyết định**: không duyệt, chấp nhận, công nhận, ghi LMS. Quyền quyết định nằm ở BE (state machine).
  Các agent một-lượt (chuẩn hóa hồ sơ, giám sát, tiền thẩm) **không có công cụ ghi**: BE gửi dữ liệu đã che PII, nhận kết luận cấu trúc rồi tự kiểm và ghi.
- **Mọi đổi trạng thái đi qua `domain/statemachine`** và ghi audit cùng transaction; repository dùng `infrastructure/persistence/transitions.py` (`lock_status`/`set_status`).
- **Bảng `lms_*` chỉ `infrastructure/lms` được đụng**; nghiệp vụ chỉ thấy `LmsPort`, sinh viên khớp bằng mã sinh viên. Ghi LMS chỉ qua `credit_sync_job` tạo trong transaction QTV phê duyệt.
- **Mọi bảng mới phải bật RLS** (Supabase mở schema `public` qua khóa anon) — có test chặn.
- **Migration đã áp dụng thì không sửa** (checksum lệch): thêm `V<n+1>__...sql` mới.
- **Prompts**: nằm ở `agent/prompts/*.md` (external file, `{{placeholder}}`). KHÔNG nhúng prompt dài trong Python string.
- **Ràng buộc đề tài** (chi tiết ở `docs/problem-statement.md`):
  - Phê duyệt đề cương thực tập, xử lý ngoại lệ, công nhận quy đổi tín chỉ BẮT BUỘC có
    giảng viên/quản trị viên phê duyệt (HITL) — agent không được tự quyết.
  - Câu trả lời về chính sách phải trích dẫn đúng văn bản quy định hiện hành.
  - Bảo mật thông tin sinh viên và doanh nghiệp (che PII trước khi gửi LLM ngoài).
- **Logging hooks**: `.claude/.cursor/.codex/.gemini/.agents/.github` auto-log prompt vào
  `.ai-log/`. KHÔNG disable, KHÔNG bypass `--no-verify`. Đừng dán khóa/mật khẩu vào prompt (sẽ bị ghi log).

## Tài liệu và cấu hình còn của dự án cũ (KHÔNG tin)

Các file sau mô tả app cũ (một app `src/`, SQLAlchemy/SQLite, LangGraph, SPA `web/`, `.kiro/`, `docs/PRD.md` — đều đã bỏ khỏi nhánh `konan`).
Không dùng làm căn cứ; khi đụng tới thì cập nhật hoặc xóa:
- `README.md`, `README_boilerplate.md`, `ARCHITECTURE.md`, `PROJECT_CONTEXT.md`, `presentation/`, `scripts/check_docs.py`, `scripts/llm_e2e.py`.
- `deploy/` (Caddy, Keycloak, compose LLM) và `.github/workflows/cd-ec2.yml` (build từ Dockerfile gốc và `deploy/docker-compose.production.yml` không còn tồn tại).
- `docs/guide/` là tài liệu khóa học (tham khảo chung), không phải đặc tả của dự án.
- Docker (`be/Dockerfile`, `agent/Dockerfile`, `docker-compose.yml`) mới viết, chưa build thử; dev hằng ngày không dùng.

## Quy tắc viết tài liệu (docs)

- **Làm xong một chức năng/refactor thì viết tài liệu** vào `docs/changes/`, một file `.md`. Có thể viết
  ngay khi vừa xong hoặc ngay trước khi commit — miễn là có trước khi kết thúc công việc.
- **Tên file**: `YYYYMMDD-<làm-cái-gì>.md` (kebab-case, ngày là ngày làm), ví dụ
  `docs/changes/20261114-refactor-fe.md`.
- **Nội dung**: vấn đề/mục tiêu, đã làm gì (cấu trúc, file chính), cách kiểm tra, và những gì
  chưa kiểm tra hoặc còn lưu ý.
- **Người dùng yêu cầu chỉnh sửa lại tính năng đã có tài liệu → SỬA file docs đó**, không tạo file
  `.md` mới cho cùng tính năng. Cập nhật nội dung cho khớp code; chỉ tạo file mới khi là tính năng khác.
- Đổi cấu trúc hoặc trạng thái triển khai thì cập nhật mục "Trạng thái hiện tại" ở trên và README của `be/`/`agent/`.

## Quy tắc commit / PR

- **KHÔNG** thêm `Co-Authored-By: Claude ...` vào commit message và **KHÔNG** thêm dòng
  "Generated with Claude Code" vào mô tả PR. Viết message thuần, không kèm trailer attribution nào.
- **Khi sửa theo review/CI (Auto-fix)**: chỉ sửa code, chạy kiểm tra, commit và push. **KHÔNG** đăng comment
  hay reply trên PR/thread review, và không cần resolve thread (kể cả dòng "Addressed by Claude Code").
  Giải thích gì thêm thì nói với người dùng trong phiên làm việc.
- Chỉ commit/push khi người dùng yêu cầu. Không commit `.env` hay file chứa khóa.

## Quyết định kỹ thuật (ADR ngắn)

- **Tách agent thành service riêng**: cổng riêng, vòng đời riêng, khóa LLM chỉ nằm ở agent → BE nhỏ, dễ kiểm, ranh giới HITL rõ.
- **Postgres (Supabase) + migration SQL**: không dùng ORM; mỗi thực thể một repository, schema nằm trong `resources/db/migration`.
  Kết nối qua Session pooler (IPv4); host trực tiếp `db.<ref>.supabase.co` chỉ có IPv6.
- **Defence-in-depth cho HITL**: agent không được cấp công cụ quyết định, và state machine từ chối actor không phải người.
- **LLM: OpenAI trực tiếp, proxy dự phòng**: không chuyển sang dự phòng khi lỗi khóa/yêu cầu (401/400) để không che lỗi cấu hình.
