# Trợ lý điều hướng nâng cao: trang đang mở, trang chi tiết hồ sơ, bộ lọc

Ngày: 2026-11-23. Tiếp nối `docs/changes/20261122-ui-lms-va-side-chat.md` (tool `navigate_to` bản đầu).

## Vấn đề

`navigate_to` chỉ mở được trang tĩnh trong menu. Trợ lý:
1. không biết người dùng đang ở trang nào, nên không trả lời được "trang này để làm gì / ở đây làm gì tiếp";
2. không mở được trang chi tiết hồ sơ `/lecturer|admin/internships/[id]` ("mở hồ sơ của bạn An");
3. không mở được trang kèm bộ lọc ("hàng chờ chỉ đề cương", "cờ rủi ro đã giải quyết").

## Đã làm

Nguyên tắc giữ nguyên: agent không biết URL (FE là nơi duy nhất giữ URL), BE lọc hành động trước khi chuyển cho trình duyệt,
quyền xem hồ sơ do BE kiểm khi trang tải.

**Hợp đồng** (`.kiro/specs/agent-hoi-dap/contract.md`):
- `final.actions[]`: `{type:"navigate", page, label, internship_id?, filters?{khóa: giá trị}}`.
- FE→BE `ask` thêm `page?{key, internship_id?}`; BE chuyển thành `start.current_page`.

**Agent**
- `policy_assistant/pages.json`: trang mới `internship_detail` cho GV/QTV (`menu: false`, `param: "internship_id"`);
  `filters` cho `queue` (`kind`), `internships` (`status`, `milestone`, `milestone_status`, `flagged`), `flags` (`status`, có `all`).
- `pages.py`: `Page.param`, `Page.filters` (`PageFilter`), `find_page()`.
- `tools/navigate.py`: schema thêm `internship_id` và `filters` (enum theo vai trò). Lỗi `missing_internship_id` khi thiếu mã;
  `unknown_internship` khi mã chưa có trong kết quả tool của lượt này (chống bịa mã); `invalid_filter` khi khóa/giá trị không thuộc trang.
- `core/tools.py` `TurnContext.seen_internship_ids`: `StaffTool` gom `id`/`internship_id` từ kết quả `list_internships`/hàng chờ/cờ;
  mã hồ sơ của trang đang mở cũng được tính ("mở lại hồ sơ này").
- `list_internships` thêm tham số `student` (tên hoặc mã SV).
- `protocol.py`: `CurrentPage`, `StartFrame.current_page`, `Action.internship_id/filters`.
- `agent.py`: dòng `{{current_page}}` trong prompt ("Người dùng đang mở trang: … [, hồ sơ mã N]"); khóa lạ với vai trò thì bỏ trống.
- Prompts: `policy_assistant.system.md` (hiểu "trang này"), `persona.lecturer.md`/`persona.admin.md` (mở hồ sơ một SV: gọi
  `list_internships(student=…)` trước; 1 kết quả thì mở, nhiều thì hỏi lại; điều kiện lọc thì truyền `filters`), `persona.student.md` (mục g: hỏi về trang đang mở).

**BE**
- `service/agent/assistant_orchestrator.py`: `valid_actions()` nhận thêm `internship_id`/`filters` (trường sai thì bỏ riêng trường đó);
  `valid_current_page()`; `run_turn(..., current_page=)` đưa vào khung `start`.
- `presentation/controller/assistant_controller.py`: chuyển `frame["page"]` vào `run_turn` (trang sai định dạng chỉ bị bỏ, không từ chối câu hỏi).
- `service/agent/agent_staff_reads.py`: lọc `student` theo đầu từ, không dấu (dùng `normalize` của `policy_search_service`):
  "an" khớp "Nguyễn Văn An" nhưng không khớp "Trần"/"Toàn"; hoặc mã SV chứa chuỗi tìm. Nối qua `agent_tool_service` và
  `GET /api/agent-tools/staff/internships?student=`.

**FE**
- `lib/nav.ts`: `NavItem.filters` (khóa query trang đọc), `DETAIL_PAGES`, `pageHref(role, key, {internshipId, filters})`
  (trang chi tiết cần mã hợp lệ; chỉ giữ khóa lọc khai báo, giá trị được mã hóa), `findCurrent` trả `key`, `currentPageRef()`.
- `AssistantProvider.tsx`: bọc `ask` để gửi kèm trang đang mở (`usePathname`), điều hướng với mã/bộ lọc. `ChatThread.tsx`: link "Đã mở" đúng URL.
- `QueuePanel.tsx` (`?kind=`), `InternshipList.tsx` (`?status=&milestone=&milestone_status=&flagged=true`), `FlagsPanel.tsx` (`?status=`):
  đọc bộ lọc ban đầu từ URL (giá trị lạ thì mặc định), bọc `Suspense` ngay trong component; query đổi thì dựng lại phần thân bằng `key`
  (không dùng `setState` trong effect). Đổi bộ lọc bằng tay trên trang không ghi lại URL.

## Test đã viết (CHƯA chạy)

- Agent `tests/test_policy_assistant.py`: trang chi tiết thiếu mã / mã bịa / mã lấy từ `list_internships`; bộ lọc sai khóa, sai giá trị, hợp lệ;
  schema chỉ GV/QTV có `internship_id`/`filters`; trang đang mở vào prompt và mở lại được; trang lạ bị bỏ. Hàm `_final_actions` bỏ trường rỗng.
  `tests/test_prompts.py`: placeholder `current_page`.
- BE `tests/service/test_assistant_orchestrator.py`: `valid_actions` với mã/bộ lọc; `current_page` hợp lệ/không hợp lệ trong khung `start`.
  `tests/service/test_agent_staff_reads.py`: lọc `student` (có dấu, không dấu, hoa thường, mã SV, đầu từ).
- FE `lib/nav.test.ts`: `pages.json` ↔ `nav.ts` (trang ngoài menu ↔ `DETAIL_PAGES`, khóa bộ lọc ↔ `NavItem.filters`), `pageHref` với mã/bộ lọc,
  `currentPageRef`. `AssistantProvider.test.tsx`: URL chi tiết, query bộ lọc, `ask` gửi kèm `page`.

## Cách kiểm tra

1. `make test`, `make lint`, `cd fe && npx tsc --noEmit`.
2. Restart BE + agent (tool/prompt mới), `scripts/start.sh`, đăng nhập dev vai trò giảng viên, mở ngăn Trợ lý (Ctrl+J):
   - "mở hồ sơ của <tên SV trong seed>" → `/lecturer/internships/<id>`;
   - "mở cờ rủi ro đã giải quyết" → `/lecturer/flags?status=resolved`, nút "Đã giải quyết" đang chọn;
   - "mở hàng chờ, chỉ đề cương" → `/lecturer?kind=outline`;
   - vai trò sinh viên, đang ở Đề cương, hỏi "trang này để làm gì?" → trả lời về trang Đề cương.

## Chưa làm / lưu ý

- Chưa chạy test/lint/tsc, chưa thử với LLM thật (mô hình có gọi `list_internships` trước khi mở hồ sơ không).
- Bộ eval (`agent/tests/eval/cases.yaml`) chưa có ca điều hướng: runner chưa hỗ trợ `current_page` và kiểm `actions`.
- Tìm theo **mã SV** có thể không chạy nếu cấu hình `PII_STUDENT_ID_PATTERN` (agent che mã SV trong câu hỏi trước khi gửi LLM); tìm theo tên thì được.
- Agent chưa có tool đọc chi tiết MỘT hồ sơ theo mã: ở trang chi tiết, "hồ sơ này" chỉ dùng được để mở lại/điều hướng, chưa tóm tắt được nội dung.
- Sinh viên chưa có bộ lọc/trang chi tiết (không cần: mỗi SV một hồ sơ).
