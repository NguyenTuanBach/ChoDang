# Tasks — Agent hỏi đáp (Trợ lý chính sách)

> Kiro spec · Giai đoạn 3/3 · Bản nháp 0.1 · 2026-11-21. Truy vết về `requirements.md` và `design.md`.
> Quy ước: chỉ gồm việc viết/sửa/kiểm thử **code**; làm theo thứ tự, viết **test trước** rồi mới code; mỗi task nối vào task trước, không để code mồ côi. Task có `*` là tùy chọn.
> Việc không phải code (tài liệu `docs/changes/…` theo `CLAUDE.md`, chốt model/pháp chế, kiểm tay) làm riêng, không nằm trong danh sách này.
> Lệnh kiểm: `make agent-test`, `make agent-lint`, `make be-test` (hoặc `make test`, `make lint`).

## Phase 0 — Lõi agent (không cần BE thật, LLM giả, BE giả)

- [x] 1. Cấu hình và `AiClient` mở rộng
  - [x] 1.1 Test rồi thêm vào `Settings`: `OPENAI_EMBEDDING_MODEL`, `AGENT_MAX_ROUNDS` (6), `AGENT_MAX_TOOL_CALLS` (8), `AGENT_TURN_SECONDS` (25), `BE_URL`, `PII_STUDENT_ID_PATTERN`; cập nhật `.env.example`. Nhiệt độ mặc định riêng cho trợ lý (≈ 0.2).
  - [x] 1.2 Test rồi mở rộng `ChatResult` (`tool_calls`, `finish_reason`) và `AiClient.chat(...)` nhận `tools`, `tool_choice`, tham số theo từng lần gọi; model suy luận bỏ `temperature`, nới trần token.
  - [x] 1.3 Test rồi thêm streaming trả async iterator `Delta` cho lượt trả lời cuối.
  - [x] 1.4 Test rồi thêm `AiClient.embed(texts)`.
  - [x] 1.5 Test rồi thêm khai báo khả năng theo endpoint (`tools`, `stream`, `embed`) và `supports()`; chuyển dự phòng chỉ sang endpoint đủ khả năng, không có thì `LlmUnavailableError`. Giữ nguyên hành vi không-fallback với 400/401/403.
  - _Requirements: R1.1, R12.1, R12.4, R17.3, R17.4_

- [x] 2. Khung tool
  - [x] 2.1 Test rồi viết `Tool` (Protocol, `read_only: Literal[True]`), `ToolSpec`, `ToolResult`, `ToolRegistry`, `to_openai_schema()`; bọc kết quả trong `<tool_result>`.
  - [x] 2.2 Test kiến trúc: mọi tool `read_only`, không schema nào có trường chủ thể (P1, P2); chạy trên registry của mọi agent.
  - _Requirements: R5.2, R7.1, R8.4_

- [x] 3. Che PII
  - [x] 3.1 Test rồi viết `PiiRedactor` (email, SĐT VN, MST, mã SV theo cấu hình) trả văn bản đã che + ánh xạ nhãn; không khôi phục nhãn mặc định.
  - [x] 3.2 Test thuộc tính P6: văn bản chứa PII mẫu thì kết quả không còn giá trị gốc; log/trace chỉ nhận bản đã che.
  - _Requirements: R11.1, R11.3, R11.4_

- [x] 4. Prompt
  - [x] 4.1 Viết `core/prompts.py` (`PromptLoader`: đọc `prompts/*.md`, cache, thay `{{placeholder}}`, báo lỗi khi thiếu/thừa placeholder) kèm test.
  - [x] 4.2 Xóa ba prompt cũ và `prompts/README.md`; viết `policy_assistant.system.md`, `citation_rules.md`, `safeguards.md`, `refusals.md` (nội dung theo `docs/thiet-ke-agent-hoi-dap.md` mục 9); test dựng prompt đầy đủ với dữ liệu mẫu, kiểm có đủ các khối `<role>`, `<workflow>`, `<rules>`, `<safeguards>`.
  - _Requirements: R8.5, R17.1, R17.2, R17.5_

- [x] 5. Vòng lặp agent
  - [x] 5.1 Test (LLM giả) rồi viết `agent_loop`: gọi LLM → chạy `tool_calls` → nối kết quả → lặp, phát `status/tool_call/tool_result`.
  - [x] 5.2 Giới hạn vòng/lần gọi tool/thời gian, kết thúc có kiểm soát (P7).
  - [x] 5.3 Chạy tool độc lập song song; tool lỗi hoặc quá hạn trả `ToolResult(ok=False)` cho LLM.
  - [x] 5.4 Hủy qua `cancel`/đóng kết nối bằng `TaskGroup` (P12).
  - [x] 5.5 `TurnTrace`: bước, tool, độ trễ, token, provider.
  - _Requirements: R1.1–R1.7, R10.4_

- [x] 6. Hậu kiểm câu trả lời
  - [x] 6.1 Test rồi viết `CitationVerifier` (id ∈ `seen_chunks`, ≤ 5, bỏ id lạ; thay phần mất nguồn bằng mẫu "không tìm thấy căn cứ") và `build_citations` (P3).
  - [x] 6.2 Test rồi viết `NumberChecker` (số/thời hạn phải có trong nguồn) (P10).
  - [x] 6.3 Test rồi viết `CommitmentGuard` (cụm cam kết → viết lại theo mẫu B4).
  - [x] 6.4 Thêm cảnh báo khi chunk `is_sample=true`.
  - _Requirements: R4.1–R4.7, R7.3_

- [x] 7. Chế độ suy giảm
  - [x] 7.1 Test (LLM giả luôn lỗi) rồi viết `degraded_answer`: gọi `search_policy` chỉ bằng từ khóa, trả nguyên văn top chunk + mẫu thông báo, `degraded=true` (P9).
  - _Requirements: R12.1–R12.3_

- [x] 8. `PolicyAssistant` và các tool tra quy định phía agent
  - [x] 8.1 Viết `BeToolsClient` (httpx; service token, `X-On-Behalf-Of` nếu có; timeout; ánh xạ lỗi) kèm test với BE giả.
  - [x] 8.2 Viết `search_policy` (embed query → gửi `{query, query_vector?, top_k}`; thiếu vector thì từ khóa) và `get_policy_clause`; ghi các chunk nhận được vào `seen_chunks`.
  - [x] 8.3 Viết `PolicyAssistant.run(start)` nối PII → prompt → vòng lặp → hậu kiểm → `final` (stream `token`), test end-to-end với LLM giả + BE giả cho các nhóm: câu có căn cứ, `no_match`, đòi quyết định, từ chối.
  - _Requirements: R1, R2.1–R2.7, R4, R7, R8_

- [x] 9. Endpoint WebSocket của agent
  - [x] 9.1 Test rồi viết `WS /v1/policy-assistant/ws`: kiểm service token lúc bắt tay, nhận `start`, phát khung, nhận `cancel`, đóng 1000/4401; giới hạn kích thước khung.
  - [x] 9.2 Viết `POST /v1/embeddings` (cần service token) cho BE nạp chunk.
  - [x] 9.3 Nối vào `create_app`; `GET /v1/info` liệt kê agent `policy_assistant`; cập nhật test kiến trúc (agent không import `vin15`, `openai` chỉ trong `core/`).
  - _Requirements: R9.1, R9.3, R9.5, R9.6, R9.9, R3.3_

## Phase 1 — BE: kho quy định và tool tra quy định

- [x] 10. Schema kho quy định
  - [x] 10.1 Viết `V2__policy_library.sql` (extension `vector`, `unaccent`, `btree_gist`; `policy_document`, `policy_version` có ràng buộc không chồng hiệu lực, `policy_chunk` có `tsv` và `embedding vector(1536)`; RLS mọi bảng).
  - [x] 10.2 Test tích hợp migration trên Postgres: áp dụng được, RLS bật, ràng buộc chồng hiệu lực chặn đúng (P14).
  - _Requirements: R3.1, R3.5, R3.7_

- [x] 11. Tách văn bản và nạp
  - [x] 11.1 Test rồi viết `PolicyChunker` (Markdown/văn bản thuần theo "Điều N." / "Khoản M.", giữ tiêu đề điều, sinh `chunk_id` ổn định).
  - [x] 11.2 Viết `PolicyRepository` và `PolicyIngestService` (tạo `draft`, gọi agent `/v1/embeddings` theo lô, lưu `embedding_model`); thêm `AgentApiClient.embed()`.
  - [x] 11.3 Viết `PolicyPublishService` (xuất bản, đóng `effective_to` bản cũ, `superseded`, audit) + test.
  - [x] 11.4 Viết `policy_admin_controller` (nạp, xem trước, xuất bản) — chỉ vai trò `admin`; test quyền.
  - _Requirements: R3.2–R3.4_

- [x] 12. Tìm kiếm lai
  - [x] 12.1 Test trên dữ liệu mẫu rồi viết `PolicySearchService.search` (lọc hiệu lực theo `Asia/Ho_Chi_Minh`, từ khóa, vector, RRF, τ → `no_match`) (P4).
  - [x] 12.2 Test chế độ chỉ từ khóa khi không có vector; test chunk thuộc bản hết hiệu lực/`draft` không bao giờ xuất hiện.
  - [x] 12.3 Viết `get_chunk(chunk_id, with_neighbors)` + test `not_found`.
  - _Requirements: R2.1–R2.7_

- [x] 13. Endpoint tool tra quy định và xác thực tool
  - [x] 13.1 Test rồi mở rộng `ActorTokenService`: claim `scope`, kiểm phạm vi (agent-token không dùng ở API thường và ngược lại).
  - [x] 13.2 Viết `AgentSubjectResolver` (service token → agent-token → người dùng mặc định ở dev → 401) và `AGENT_DEV_DEFAULT_USER_EMAIL`; `validate_production()` từ chối khi đặt ở production (P11).
  - [x] 13.3 Viết `agent_tools_controller`: `POST /api/agent-tools/policy/search`, `GET /api/agent-tools/policy/chunks/{id}`; mỗi lời gọi ghi `audit_event` (P8); chỉ phương thức chỉ-đọc (P1).
  - _Requirements: R6.1–R6.5, R16.1–R16.4_

- [x] 14. Seed bộ quy chế mẫu
  - [x] 14.1 Soạn bộ quy chế mẫu (dạng Markdown trong repo, theo mục 9 của tài liệu nghiệp vụ) và `seed_dev.py` phần quy chế (`is_sample=true`, gọi nạp + xuất bản); `make seed-dev`; từ chối khi `APP_ENV=production`; chạy lại được (P13).
  - _Requirements: R3.6, R16.5, R16.6_

## Phase 2 — Chat đầu-cuối (BE ↔ agent ↔ FE)

- [x] 15. Lưu hội thoại
  - [x] 15.1 Viết `V3__assistant_chat.sql` (`chat_conversation`, `chat_message`, RLS) + test migration.
  - [x] 15.2 Viết `ChatRepository` và API `GET /api/assistant/conversations`, `GET /api/assistant/conversations/{id}` (chỉ chủ sở hữu) + test chéo người dùng.
  - _Requirements: R10.1, R10.3, R10.5_

- [x] 16. Điều phối lượt hỏi ở BE
  - [x] 16.1 Viết `AgentApiClient.chat()` (WebSocket bằng `websockets`, service token, async iterator khung, `cancel`); thêm phụ thuộc vào `be/pyproject.toml`; test với agent giả.
  - [x] 16.2 Viết `AssistantOrchestrator`: cắt + che PII lịch sử, cấp agent-token (scope, ≈ 5 phút) hoặc dùng người dùng mặc định ở dev, chuyển tiếp khung, lưu `final`/`trace`/audit kể cả khi FE đã rớt.
  - _Requirements: R9.4, R9.6, R9.7, R10.1, R10.2, R10.4_

- [x] 17. WebSocket FE ↔ BE
  - [x] 17.1 Test rồi viết `POST /api/assistant/ws-ticket` (một lần, ≈ 30 s, RAM) và `WS /api/assistant/ws`: `auth` trong ≈ 5 s, kiểm `Origin`, `ask`/`cancel`/`ping`, `busy`, ping/pong, đóng khi im lặng, trần kích thước khung.
  - [x] 17.2 Giới hạn tần suất: rule cho `ws-ticket` (middleware sẵn có) và giới hạn `ask`/phút + số kết nối/người trong handler; test `rate_limited` không gọi LLM.
  - _Requirements: R9.1–R9.9, R13.1–R13.3_

- [x] 18. FE trang chat
  - [x] 18.1 Viết reducer trạng thái chat theo `turn_id` (đang chạy, bước, token, citations, degraded, lỗi) kèm test.
  - [x] 18.2 Viết hook WebSocket (ticket → `auth` → `ask`, nối lại có backoff + tải lại hội thoại, `cancel`) kèm test; cấu hình `NEXT_PUBLIC_BE_WS_URL` nếu `rewrites` không chuyển được WebSocket.
  - [x] 18.3 Viết giao diện chat: tiến trình, stream, danh sách trích dẫn bấm xem nguyên văn, cảnh báo văn bản mẫu/`degraded`, thông báo lỗi; test thành phần.
  - _Requirements: R15.1–R15.5_

- [x] 19. Kiểm thử đầu-cuối tự động
  - [x] 19.1 Test tích hợp BE + agent (LLM giả): hỏi một câu có căn cứ → `final` có `citations` đúng; `no_match` → mẫu "không tìm thấy"; LLM giả lỗi → `degraded`; `cancel` giữa chừng.
  - _Requirements: R1, R4, R9, R12_

## Phase 3 — Tool ngữ cảnh cá nhân

- [x] 20. Schema nghiệp vụ tối thiểu và dữ liệu giả
  - [x] 20.1 Viết `V4__internship_minimal.sql` (`internship`, `milestone`, `journal_entry`, `evidence`, `request`; tên/cột theo `docs/nghiep-vu-thuc-tap.md` mục 6 và 9; RLS) + test migration.
  - [x] 20.2 Mở rộng `seed_dev.py`: 1 QTV, 1 GV, ≥ 2 SV ở trạng thái khác nhau (A: trễ một mốc, thiếu nhật ký; B: đã nộp báo cáo cuối) kèm mốc/nhật ký/minh chứng; idempotent, từ chối ở production (P13).
  - _Requirements: R5, R16.5, R16.6_

- [x] 21. Dịch vụ đọc và tính điều kiện tín chỉ
  - [x] 21.1 Test rồi viết truy vấn đọc: hồ sơ, mốc (hạn, trạng thái, việc cần làm tiếp), tiến độ nhật ký/minh chứng, yêu cầu — chỉ theo chủ thể.
  - [x] 21.2 Test rồi viết `CreditChecklistService` tính T1–T6 (T6 từ adapter LMS giả trả dữ liệu cố định) với số liệu so ngưỡng; ngưỡng lấy từ cấu hình/quy chế mẫu.
  - _Requirements: R5.1, R5.4_

- [x] 22. Endpoint tool cá nhân (BE)
  - [x] 22.1 Test rồi viết `GET /api/agent-tools/me/{internship,milestones,progress,credit-checklist,requests}` chỉ trả trường tối thiểu (không email/SĐT/MST); chưa có hồ sơ → `available=false, reason=no_internship_record`; giảng viên/quản trị bị từ chối.
  - [x] 22.2 Test thuộc tính P5: với token của SV A không có đường nào trả dữ liệu SV B; audit mỗi lời gọi (P8).
  - _Requirements: R5.2, R5.3, R5.5, R5.7, R6.4, R6.6_

- [x] 23. Tool cá nhân phía agent
  - [x] 23.1 Viết các tool `get_my_*` (không tham số chủ thể) và đăng ký theo vai trò (sinh viên có, giảng viên/quản trị không); test P1, P2.
  - [x] 23.2 Test với LLM giả + BE giả: câu hỏi kết hợp quy định + tình trạng cá nhân gọi đủ hai nhóm tool và đối chiếu số liệu; không có hồ sơ thì trợ lý nói rõ chưa xem được.
  - _Requirements: R5.1–R5.7_

## Phase 4 — Đánh giá và hoàn thiện

- [x] 24. Bộ đánh giá
  - [x] 24.1 Viết bộ 40–60 câu (`agent/tests/eval/cases.yaml`) theo sáu nhóm ở R14.2, kèm điều khoản kỳ vọng trên bộ quy chế mẫu và dữ liệu giả.
  - [x] 24.2 Viết runner `make agent-eval` (LLM thật, không chạy trong CI mặc định) báo các chỉ số R14.3; kiểm tool ghi/đổi trạng thái = 0 qua trace.
  - [x] 24.3 Test tất định (LLM giả) cho runner: tính chỉ số đúng trên kết quả mẫu.
  - _Requirements: R14.2–R14.4_

- [x] 25. Chỉnh theo kết quả đo
  - [x] 25.1 Đưa ngưỡng τ vào cấu hình (`POLICY_NO_MATCH_THRESHOLD`) và test `no_match` với τ khác nhau.
  - [x] 25.2 Thêm ghi vết/tra cứu theo `trace_id` (`GET /api/assistant/traces/{id}` chỉ chủ sở hữu hoặc QTV) + test.
  - _Requirements: R14.1, R14.5_

- [ ] 26.* Người chấm bám nguồn (tùy chọn)
  - [ ] 26.1* Thêm lượt LLM thứ hai kiểm "mỗi nhận định có được chunk đã trích hỗ trợ không", bật bằng cấu hình; test với LLM giả; đo thêm độ trễ để so với NF1.
  - _Requirements: R4.2, R4.5_

- [ ] 27.* Bộ nạp DOCX/PDF (tùy chọn, chờ Q3)
  - [ ] 27.1* Mở rộng `PolicyIngestService` nhận DOCX/PDF, chuyển về văn bản rồi qua `PolicyChunker`; test với tệp mẫu.
  - _Requirements: R3.2_

## Thứ tự và phụ thuộc

```
P0 (1→9)  ──►  P1 (10→14)  ──►  P2 (15→19)  ──►  P4 (24→26)
                    │
                    └────────────►  P3 (20→23)  ──►  P4
```
- Phase 0 độc lập BE và làm được ngay.
- Phase 1 cần Phase 0 (task 9.2 `/v1/embeddings`) cho nạp chunk; không cần đăng nhập (dùng người dùng mặc định, task 13.2).
- Phase 3 độc lập Phase 2 về mặt code, nhưng test đầu-cuối của nó cần task 19.
