# Trợ lý hỏi đáp: phân biệt vai trò, văn phong theo vai trò, tool dữ liệu cho GV/QTV

## Vấn đề
Trợ lý dùng một prompt chung viết cho sinh viên; giảng viên/quản trị viên chỉ có tool tra quy định. Vai Giảng viên hỏi
"có bao nhiêu sinh viên đang bị chậm thực tập" bị từ chối bằng câu "Mình chỉ hỗ trợ thông tin của chính bạn" (nhánh `refuse:other_user`).

## Đã làm
**Agent (`agent/`)**
- `prompts/policy_assistant.system.md`: chỉ còn phần chung; nhận `{{persona}}` và `{{role_workflow}}`. Bỏ `<answer_format>` (chuyển vào persona).
- `prompts/persona.{student,lecturer,admin}.md` (mới): mỗi tệp có `<part id="persona">` (xưng hô, giọng, cấu trúc câu trả lời) và `<part id="workflow">` (phân loại câu hỏi theo vai trò).
  SV: gần gũi, "mình"–"bạn", từng bước; GV: lịch sự, súc tích, số liệu trước, "thầy/cô"; QTV: trang trọng, ngắn gọn, thiên về số liệu tổng hợp.
- `prompts/safeguards.md`: quy tắc phạm vi dữ liệu theo vai trò (không còn "chỉ dữ liệu của chính người hỏi" cho mọi người).
- `prompts/refusals.md`: thêm `other_user_staff`, `out_of_scope_staff`, `no_basis_staff`, `no_basis_partial_staff`.
- `policy_assistant/agent.py`: nạp persona theo `actor.role`; chọn mẫu câu cố định theo nhóm vai trò (`<key>_staff`); hậu kiểm không ép `no_basis` khi câu trả lời dựa trên tool dữ liệu
  (thay tiền tố `get_my_` bằng `ctx.data_tool_names`); nhắc tra quy định (`_policy_lookup_nudge`) chỉ áp cho sinh viên.
- `policy_assistant/tools/staff.py` (mới): `get_staff_queue`, `list_risk_flags`, `get_dashboard_summary`, `list_internships` (chỉ tham số lọc, không tham số chủ thể).
  `registry.py` cấp cho `lecturer`/`admin`; `be_client.py` thêm `staff()`; `core/tools.py` thêm cờ `data_source` và `ToolRegistry.data_tool_names()`.

**BE (`be/`)**
- `service/agent/agent_staff_reads.py` (mới): tái dùng `ReportService`/`MonitoringService` nên phạm vi do BE quyết từ người dùng của agent-token; tối đa 30 mục; không email/SĐT/MST.
- `AgentToolService.staff_*` (`staff_only=True`, sinh viên → `forbidden_role`, vẫn ghi audit); `GET /api/agent-tools/staff/{queue,flags,dashboard,internships}`; nối trong `config/container.py`.

## Kiểm tra
- Đã kiểm: import module, render 3 prompt theo vai trò (không sót placeholder).
- Đã viết test nhưng **chưa chạy**: `agent/tests/test_policy_assistant.py` (persona theo vai trò, mẫu từ chối theo nhóm, GV trả lời từ tool dữ liệu không cần `[cite]`, lọc tham số, nudge chỉ cho SV),
  `test_prompts.py`, `test_policy_tools.py`; BE `tests/service/test_agent_staff_reads.py`, `tests/presentation/test_agent_tools.py` (staff 403 cho SV, 200 cho GV/QTV, có audit).
- Smoke tay đề xuất: `scripts/start.sh`, `make seed-dev`, đăng nhập dev từng vai trò tại `/login`, hỏi "có bao nhiêu sinh viên đang bị chậm thực tập" ở `/assistant`.

## Chưa làm / lưu ý
- Chưa thêm ca eval cho GV/QTV vào `tests/eval/cases.yaml`: `make agent-eval` dùng "người dùng mặc định" (sinh viên) ở BE nên tool staff sẽ bị 403; cần cách cấp agent-token theo vai trò cho eval.
- Tool staff trả **tên sinh viên** (không email/SĐT/MST) cho LLM ngoài để GV gọi đúng người; nếu cần chặt hơn, chỉ trả mã hồ sơ và để FE hiển thị tên.
- Prompt GV/QTV chưa thử với LLM thật. Sidetab và điều hướng (`navigate_to`) là việc riêng, chưa làm.
