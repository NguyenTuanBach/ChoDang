# Requirements — Agent hỏi đáp (Trợ lý chính sách)

> Kiro spec · Giai đoạn 1/3 (Requirements → Design → Tasks) · Bản nháp 0.1 · 2026-11-21.
> Tiêu chí nghiệm thu dùng **EARS**: `WHEN … THEN … SHALL`, `IF … THEN … SHALL`, `WHILE …`, `WHERE …`, hoặc `SHALL` không điều kiện.
> Nguồn: `docs/nghiep-vu-thuc-tap.md` (nhóm B, X, mục 8), `docs/problem-statement.md`, bản thiết kế sơ bộ `docs/thiet-ke-agent-hoi-dap.md`.
> Mã `B*`, `X*`, `N*`, `D*`, `R*` ở cuối mỗi requirement là mã nghiệp vụ gốc để truy vết.

## 1. Giới thiệu

Giảng viên và phòng đào tạo bị quá tải bởi các câu hỏi lặp lại về thủ tục, thời hạn và điều kiện công nhận tín chỉ. Tính năng này là **trợ lý hỏi đáp** cho người dùng của hệ thống thực tập: một **agent thật**, tự lập kế hoạch, tự chọn và gọi nhiều tool, để:

1. tra **quy định đang có hiệu lực** và trả lời kèm trích dẫn điều/khoản;
2. đối chiếu quy định với **tình trạng của chính người hỏi** (hồ sơ, mốc, nhật ký);
3. không bao giờ ra quyết định thay giảng viên/quản trị viên, không xem dữ liệu người khác, không bịa.

Agent chạy ở service riêng (`agent/`, cổng 8100); BE (`be/`, cổng 8000) sở hữu dữ liệu, kho quy định, hội thoại và kiểm quyền; FE (`fe/`) chỉ nói chuyện với BE. Hỏi đáp truyền qua **WebSocket** (FE ↔ BE ↔ agent), tool là HTTP chỉ-đọc.

### 1.1. Ràng buộc cứng

| ID | Ràng buộc | Nguồn |
|---|---|---|
| C1 | Agent **không có công cụ quyết định** (duyệt, chấp nhận, công nhận, ghi LMS, tạo yêu cầu thay SV) | N1, C5, D11 |
| C2 | Câu trả lời chính sách chỉ dựa trên văn bản **đang có hiệu lực tại ngày hỏi**, kèm trích dẫn đúng | N2, B2, B6 |
| C3 | Dữ liệu ai chỉ thấy phạm vi của người đó; PII được che trước khi gửi LLM ngoài | N3, X1, X3 |
| C4 | Mọi hành động của agent có ghi vết kèm lý do | N4, C7, X2 |
| C5 | BE và agent chỉ nói chuyện qua mạng, không import code của nhau; SDK LLM chỉ ở `agent/.../core`; BE không giữ khóa LLM | `CLAUDE.md` |
| C6 | Mọi bảng mới bật RLS; migration đã áp dụng không sửa | `CLAUDE.md` |
| C7 | Prompt nằm ở `agent/prompts/*.md`, không nhúng chuỗi dài trong Python | `CLAUDE.md` |

### 1.2. Ngoài phạm vi (bản này)

- Đăng nhập thật (Google OAuth): dùng **người dùng mặc định chỉ ở dev** (R16).
- Tác tử giám sát và tiền thẩm (hai agent còn lại).
- Hỏi về quy định ở **quá khứ** (tra văn bản hết hiệu lực theo ngày tùy ý).
- Nạp văn bản DOCX/PDF (bản này nhận Markdown/văn bản thuần theo quy ước Điều/Khoản).
- Tạo yêu cầu/nháp thay sinh viên; gửi thông báo; ghi LMS.
- Giảng viên/quản trị xem dữ liệu cá nhân của sinh viên qua trợ lý (họ chỉ tra quy định).

## 2. Thuật ngữ

| Thuật ngữ | Định nghĩa |
|---|---|
| **Lượt hỏi (turn)** | Một câu hỏi của người dùng và toàn bộ quá trình agent xử lý tới câu trả lời cuối |
| **Tool** | Hàm chỉ-đọc mà LLM được phép gọi; chạy bằng HTTP tới BE |
| **Chunk** | Một đoạn văn bản quy định (một khoản, hoặc một điều nếu ngắn) có `chunk_id` ổn định |
| **Văn bản hiệu lực** | Bản `published` có `effective_from ≤ hôm nay ≤ effective_to` (hoặc `effective_to` rỗng) |
| **Văn bản mẫu** | Bản có `is_sample=true`: quy chế tự soạn, chưa phải quy chế thật (D6, R1) |
| **Agent-token** | Token ngắn hạn BE cấp cho agent trong một lượt, mang `sub` và `role` của người hỏi, `scope=agent_tools` |
| **Người dùng mặc định** | Chủ thể BE dùng khi chưa có đăng nhập, chỉ ở dev (R16) |
| **Suy giảm (degraded)** | Chế độ khi LLM không dùng được: trả nguyên văn điều khoản, không diễn giải |
| **Khung (frame)** | Một thông điệp JSON trên WebSocket, có trường `type` |

## 3. Vai trò

| Vai trò | Dùng trợ lý để |
|---|---|
| **Sinh viên** | Hỏi chính sách và tình trạng của chính mình (tool tra quy định + tool cá nhân) |
| **Giảng viên, Quản trị viên** | Hỏi chính sách (chỉ tool tra quy định). Quản trị viên còn nạp và xuất bản văn bản quy định (R3) |
| **Agent** | Tác nhân hệ thống, `actor_kind='agent'` trong audit; không phải người dùng, không có quyền quyết định |

---

## 4. Yêu cầu chức năng

### Requirement 1 — Vòng lặp agent có tool

**User story:** Là sinh viên, tôi muốn trợ lý tự tìm đúng thông tin cần thiết (nhiều bước nếu cần) rồi mới trả lời, để câu trả lời dựa trên dữ liệu thật chứ không phải phỏng đoán.

1. WHEN agent nhận khung `start` hợp lệ THEN THE SYSTEM SHALL chạy vòng lặp: gọi LLM kèm danh sách tool, thực thi các `tool_calls`, nối kết quả vào hội thoại, lặp cho đến khi LLM trả câu trả lời cuối.
2. THE SYSTEM SHALL giới hạn mỗi lượt ≤ 6 vòng LLM, ≤ 8 lần gọi tool và ≈ 25 giây tổng.
3. IF lượt vượt giới hạn THEN THE SYSTEM SHALL kết thúc có kiểm soát bằng câu trả lời tốt nhất dựng từ dữ liệu đã có hoặc mẫu "chưa xử lý được", không treo kết nối.
4. WHEN LLM yêu cầu nhiều tool độc lập trong cùng một vòng THEN THE SYSTEM SHALL chạy song song.
5. IF một tool lỗi hoặc quá hạn THEN THE SYSTEM SHALL trả lỗi có cấu trúc cho LLM như một kết quả tool (để LLM nói rõ hoặc thử cách khác), không làm sập lượt.
6. WHEN người dùng gửi `cancel` hoặc kết nối bị đóng THEN THE SYSTEM SHALL hủy vòng lặp và các lời gọi đang chạy trong thời gian ngắn, không tiếp tục gọi LLM.
7. THE SYSTEM SHALL phát khung `status`, `tool_call`, `tool_result` trong khi chạy để người dùng thấy tiến trình ("đang nghĩ").

_Truy vết: D2, B1, B7_

### Requirement 2 — Tra quy định (`search_policy`, `get_policy_clause`)

**User story:** Là người dùng, tôi muốn trợ lý tìm đúng điều khoản liên quan kể cả khi tôi diễn đạt khác với văn bản.

1. WHEN LLM gọi `search_policy` với `query` THEN THE SYSTEM SHALL chỉ tìm trong các chunk thuộc **văn bản hiệu lực tại hôm nay** (múi giờ `Asia/Ho_Chi_Minh`), do BE tự tính; không nhận ngày từ LLM hay từ agent.
2. THE SYSTEM SHALL tìm kiếm lai: từ khóa (full-text không dấu) và ngữ nghĩa (vector), trộn kết quả bằng RRF, trả tối đa `top_k` (≤ 8) chunk.
3. THE SYSTEM SHALL trả cho mỗi chunk: `chunk_id`, tên văn bản, phiên bản, điều, khoản, `effective_from`, `is_sample`, nguyên văn và điểm.
4. IF không có kết quả từ khóa và độ tương đồng ngữ nghĩa cao nhất dưới ngưỡng τ THEN THE SYSTEM SHALL trả `no_match=true` với danh sách rỗng.
5. WHERE không có vector truy vấn (embedding không khả dụng) THE SYSTEM SHALL tìm chỉ bằng từ khóa.
6. WHEN LLM gọi `get_policy_clause(chunk_id, with_neighbors)` THEN THE SYSTEM SHALL trả nguyên văn chunk đó (và chunk liền trước/sau trong cùng văn bản nếu được yêu cầu), chỉ khi chunk thuộc văn bản đang hiệu lực.
7. IF `chunk_id` không tồn tại hoặc thuộc văn bản không còn hiệu lực THEN THE SYSTEM SHALL trả lỗi `not_found`.

_Truy vết: B2, B3, B6_

### Requirement 3 — Kho văn bản quy định (BE)

**User story:** Là quản trị viên, tôi muốn nạp và xuất bản văn bản quy định có phiên bản, để trợ lý luôn dùng văn bản hiện hành.

1. THE SYSTEM SHALL lưu văn bản theo ba cấp: văn bản (`policy_document`), phiên bản (`policy_version`: nhãn, `effective_from`, `effective_to`, trạng thái `draft | published | superseded`, `is_sample`) và chunk (`policy_chunk`).
2. WHEN quản trị viên nạp văn bản Markdown/văn bản thuần THEN THE SYSTEM SHALL tách theo cấu trúc "Điều N." / "Khoản M." thành chunk, giữ tiêu đề điều cho mỗi chunk, trạng thái `draft`.
3. WHEN tách xong THEN THE SYSTEM SHALL tạo embedding cho các chunk (qua agent, vì BE không giữ khóa LLM) và lưu cùng tên model embedding.
4. WHEN quản trị viên xuất bản một phiên bản THEN THE SYSTEM SHALL đóng `effective_to` của bản cũ cùng văn bản, đánh dấu `superseded`, và ghi audit.
5. THE SYSTEM SHALL từ chối xuất bản nếu khoảng hiệu lực của các bản `published` cùng văn bản chồng nhau.
6. THE SYSTEM SHALL cung cấp lệnh seed bộ quy chế mẫu (`is_sample=true`) cho dev/test.
7. THE SYSTEM SHALL bật RLS cho mọi bảng mới của kho quy định.

_Truy vết: B6, D6, R1, C6_

### Requirement 4 — Câu trả lời có trích dẫn và hậu kiểm

**User story:** Là sinh viên, tôi muốn mỗi khẳng định về quy định có nguồn rõ ràng để tôi kiểm tra được, và không bị trả lời sai do mô hình bịa.

1. THE SYSTEM SHALL yêu cầu LLM gắn `[cite:chunk_id]` ngay sau mỗi nhận định dựa trên quy định.
2. WHEN LLM trả câu trả lời cuối THEN THE SYSTEM SHALL hậu kiểm: mỗi `chunk_id` được trích phải thuộc tập chunk đã nhận từ tool **trong lượt này**, tối đa 5; loại bỏ id lạ.
3. IF một nhận định về quy định không còn trích dẫn hợp lệ sau hậu kiểm THEN THE SYSTEM SHALL thay phần đó bằng mẫu "không tìm thấy căn cứ" thay vì giữ nhận định không có nguồn.
4. THE SYSTEM SHALL dựng danh sách `citations` trong khung `final` **từ kết quả tool** (tên văn bản, phiên bản, điều, khoản, hiệu lực, `is_sample`, trích đoạn), không từ chữ do LLM viết.
5. THE SYSTEM SHALL kiểm số liệu: mọi số/thời hạn trong câu trả lời phải xuất hiện trong chunk được trích hoặc kết quả tool; nếu lệch thì chặn hoặc sửa theo nguyên văn.
6. WHERE chunk được trích có `is_sample=true` THE SYSTEM SHALL kèm cảnh báo "căn cứ là văn bản mẫu, chưa phải quy chế chính thức".
7. IF không có chunk nào thỏa (kết quả `no_match`) THEN THE SYSTEM SHALL trả mẫu "không tìm thấy quy định" kèm hướng dẫn liên hệ giảng viên và SHALL NOT dùng kiến thức chung của LLM để lấp chỗ trống.

_Truy vết: B2, B3, B6_

### Requirement 5 — Ngữ cảnh cá nhân qua tool

**User story:** Là sinh viên, tôi muốn trợ lý biết tình trạng của tôi (mốc nào còn hạn, thiếu nhật ký tuần nào, đã đạt điều kiện nào) để trả lời đúng trường hợp của tôi.

1. THE SYSTEM SHALL cung cấp cho sinh viên các tool chỉ-đọc: `get_my_internship`, `get_my_milestones`, `get_my_progress`, `get_my_credit_checklist`, `get_my_requests`.
2. THE SYSTEM SHALL xác định chủ thể của mọi tool **ở BE** (từ agent-token, hoặc người dùng mặc định ở dev). Tool SHALL NOT có tham số nào chọn người dùng.
3. THE SYSTEM SHALL chỉ trả trường tối thiểu cần để trả lời; SHALL NOT trả email, SĐT, mã số thuế của người hướng dẫn hay doanh nghiệp.
4. THE SYSTEM SHALL do **BE** tính bảng điều kiện tín chỉ T1–T6 (đạt/chưa đạt và số liệu so với ngưỡng); agent chỉ diễn giải.
5. IF chủ thể chưa có hồ sơ thực tập THEN THE SYSTEM SHALL trả `available=false, reason=no_internship_record` và trợ lý SHALL nói rõ chưa xem được hồ sơ, không đoán.
6. WHEN câu hỏi cần cả quy định và tình trạng cá nhân THEN THE SYSTEM SHALL gọi cả hai nhóm tool và đối chiếu số liệu thật với ngưỡng trong quy định.
7. WHERE người hỏi là giảng viên hoặc quản trị viên THE SYSTEM SHALL không cung cấp các tool cá nhân (chỉ tool tra quy định).

_Truy vết: B1, D4, 9.2_

### Requirement 6 — Phạm vi dữ liệu và xác thực tool

**User story:** Là sinh viên, tôi muốn chắc chắn trợ lý không thể lộ dữ liệu của tôi cho người khác và không đọc được dữ liệu của người khác, kể cả khi bị lừa.

1. THE SYSTEM SHALL yêu cầu mọi `/api/agent-tools/*` có **service token hợp lệ**; SHALL từ chối nếu thiếu hoặc sai.
2. WHERE đã có đăng nhập THE SYSTEM SHALL yêu cầu thêm agent-token (`scope=agent_tools`, sống ≈ 5 phút, tạo cho một lượt) và lấy chủ thể từ `sub` của nó; token phiên thường SHALL NOT dùng được ở `/api/agent-tools/*`, và agent-token SHALL NOT dùng được ở API thường.
3. THE SYSTEM SHALL chỉ cho phép các phương thức chỉ-đọc (GET, hoặc POST tìm kiếm không có tác dụng phụ) ở `/api/agent-tools/*`.
4. WHEN một tool được gọi THEN THE SYSTEM SHALL ghi `audit_event` với `actor_kind='agent'`, `actor_id` = người hỏi, `entity='agent_tool'`, `action` = tên tool, kèm mã hội thoại/lượt; tham số đã che PII.
5. IF agent-token hết hạn hoặc không khớp người hỏi của lượt THEN THE SYSTEM SHALL trả 401 và ghi audit.
6. THE SYSTEM SHALL cho giảng viên/quản trị chỉ dùng tool tra quy định.

_Truy vết: B5, N3, X1, X2, C7_

### Requirement 7 — Không quyết định, không cam kết

**User story:** Là giảng viên, tôi muốn chắc chắn trợ lý không hứa kết quả xét duyệt và không thay đổi gì trong hệ thống.

1. THE SYSTEM SHALL cấp cho agent **chỉ tool đọc**; SHALL NOT có tool đổi trạng thái, duyệt, chấp nhận, công nhận, ghi LMS, tạo yêu cầu, gửi thông báo.
2. WHEN câu hỏi đòi quyết định (ví dụ "em có được công nhận tín chỉ không?") THEN THE SYSTEM SHALL giải thích quy định liên quan, nêu ai có thẩm quyền quyết, hướng dẫn cách tạo yêu cầu, và SHALL NOT cam kết hay dự đoán kết quả.
3. THE SYSTEM SHALL quét câu trả lời cuối tìm cụm cam kết ("chắc chắn được duyệt", "đã được công nhận", "em đã được…") và viết lại theo mẫu không cam kết trước khi gửi.
4. THE SYSTEM SHALL NOT tuyên bố rằng trợ lý đã nộp, duyệt hay ghi bất cứ thứ gì.

_Truy vết: B4, N1, C5, D11_

### Requirement 8 — Từ chối và an toàn

**User story:** Là quản trị viên, tôi muốn trợ lý từ chối đúng các yêu cầu không được phép và không bị thao túng qua nội dung đầu vào.

1. IF câu hỏi về dữ liệu của người khác THEN THE SYSTEM SHALL từ chối theo mẫu và ghi log.
2. IF câu hỏi yêu cầu bỏ qua quy tắc, đổi vai, lộ prompt hay công cụ nội bộ THEN THE SYSTEM SHALL từ chối theo mẫu.
3. IF câu hỏi ngoài phạm vi thực tập THEN THE SYSTEM SHALL từ chối nhẹ nhàng và nêu phạm vi trợ lý hỗ trợ.
4. THE SYSTEM SHALL bọc mọi kết quả tool trong khối dữ liệu không tin cậy và dặn LLM không làm theo chỉ thị nằm trong đó; dữ liệu do sinh viên nhập (nhật ký, mô tả công việc, tên công ty) SHALL được coi là không tin cậy.
5. THE SYSTEM SHALL dùng các mẫu từ chối/không-tìm-thấy cố định lấy từ `prompts/refusals.md`, không để LLM viết tự do các câu này.

_Truy vết: B5, B3, N3_

### Requirement 9 — Giao tiếp WebSocket và streaming

**User story:** Là sinh viên, tôi muốn thấy câu trả lời hiện dần và các bước trợ lý đang làm, và có thể bấm dừng.

1. THE SYSTEM SHALL cung cấp `WS /api/assistant/ws` ở BE cho FE và `WS /v1/policy-assistant/ws` ở agent cho BE; hai chặng dùng cùng định dạng khung JSON.
2. WHEN FE mở kết nối THEN THE SYSTEM SHALL yêu cầu khung `auth` mang `ticket` dùng một lần (≈ 30 giây) trong vòng ≈ 5 giây; sai hoặc quá hạn thì đóng kết nối mã 4401.
3. WHEN bắt tay THEN THE SYSTEM SHALL kiểm header `Origin` theo `CORS_ORIGINS` ở BE, và kiểm `Authorization: Bearer <service token>` ở agent.
4. THE SYSTEM SHALL chuyển tiếp các khung `status`, `tool_call`, `tool_result`, `token`, `final`, `error` từ agent qua BE tới FE, kèm `turn_id` và `conversation_id`.
5. THE SYSTEM SHALL cho một kết nối chạy **một lượt tại một thời điểm**; gửi `ask` khi đang chạy trả `error: busy`.
6. WHEN FE gửi `cancel` THEN THE SYSTEM SHALL chuyển `cancel` tới agent và dừng lượt.
7. IF FE rớt kết nối giữa lượt THEN THE SYSTEM SHALL vẫn chạy hết lượt và lưu `final`; FE lấy lại qua `GET /api/assistant/conversations/{id}`.
8. THE SYSTEM SHALL gửi ping/pong định kỳ (≈ 25 giây) và đóng kết nối im lặng quá ≈ 60 giây.
9. THE SYSTEM SHALL giới hạn kích thước khung từ FE (≈ 16 KB) và độ dài `question`.

_Truy vết: B7, X4_

### Requirement 10 — Lưu hội thoại và ghi vết

**User story:** Là người dùng, tôi muốn xem lại lịch sử hỏi đáp của mình; là quản trị viên, tôi muốn truy vết agent đã làm gì.

1. THE SYSTEM SHALL lưu hội thoại theo từng người dùng (`chat_conversation`, `chat_message`) gồm nội dung, `citations` và `trace` (đã che PII); chủ sở hữu duy nhất là người hỏi.
2. THE SYSTEM SHALL cắt lịch sử gửi cho agent (ví dụ 10 lượt gần nhất) và che PII trước khi gửi.
3. THE SYSTEM SHALL cho người dùng đọc lại hội thoại của chính mình và SHALL NOT cho đọc hội thoại của người khác.
4. THE SYSTEM SHALL lưu `trace` mỗi lượt: các bước, tool đã gọi, độ trễ, token, nhà cung cấp LLM, cờ `degraded`.
5. THE SYSTEM SHALL bật RLS cho các bảng hội thoại.

_Truy vết: B8, C7, X2_

### Requirement 11 — Che PII

**User story:** Là đại diện nhà trường, tôi muốn thông tin cá nhân sinh viên và doanh nghiệp không bị gửi ra LLM bên ngoài.

1. WHEN agent chuẩn bị gửi nội dung tới LLM THEN THE SYSTEM SHALL che email, số điện thoại VN, mã số thuế và mã sinh viên trong câu hỏi, lịch sử và kết quả tool, thay bằng nhãn (`[EMAIL_1]`, `[SDT_1]`…).
2. THE SYSTEM SHALL chỉ cho BE trả trường tối thiểu ở tool cá nhân (R5.3), làm lớp che thứ nhất.
3. THE SYSTEM SHALL chỉ lưu log và trace bản đã che; SHALL NOT ghi khóa LLM, service token hay agent-token vào log hay prompt.
4. THE SYSTEM SHALL NOT khôi phục nhãn PII trong câu trả lời, trừ giá trị lấy lại từ đúng trường do tool trả về.

_Truy vết: X3, N3, R2_

### Requirement 12 — Chế độ suy giảm khi LLM không khả dụng

**User story:** Là sinh viên, tôi muốn khi AI sập vẫn tra được điều khoản liên quan, thay vì nhận lỗi trống.

1. IF không đường LLM nào dùng được (chưa cấu hình, hoặc mọi đường lỗi tạm thời) THEN THE SYSTEM SHALL chuyển sang suy giảm.
2. WHEN suy giảm THEN THE SYSTEM SHALL gọi `search_policy` chỉ bằng từ khóa với câu hỏi đã che PII và trả nguyên văn các chunk đầu kèm trích dẫn, cùng dòng "Trợ lý AI đang tạm không khả dụng…".
3. WHEN suy giảm THEN THE SYSTEM SHALL đặt `final.degraded=true` và SHALL NOT chứa văn bản do LLM sinh.
4. IF đường dự phòng (proxy) không hỗ trợ tool, stream hoặc embedding THEN THE SYSTEM SHALL không chuyển sang đường đó cho các tính năng nó không hỗ trợ; không đủ thì suy giảm.

_Truy vết: X5_

### Requirement 13 — Giới hạn tần suất và tài nguyên

**User story:** Là quản trị hệ thống, tôi muốn hỏi đáp không bị lạm dụng làm cạn chi phí LLM.

1. THE SYSTEM SHALL giới hạn `POST /api/assistant/ws-ticket` bằng cơ chế rate limit sẵn có.
2. THE SYSTEM SHALL giới hạn số `ask` mỗi người mỗi phút trong handler WebSocket và số kết nối đồng thời mỗi người (ví dụ 3), vì middleware hiện có không áp dụng cho WebSocket.
3. IF vượt giới hạn THEN THE SYSTEM SHALL trả `error: rate_limited` kèm thời gian chờ và SHALL NOT gọi LLM.
4. THE SYSTEM SHALL áp trần token đầu ra và độ dài đầu vào mỗi lượt.

_Truy vết: X4_

### Requirement 14 — Quan sát và đánh giá chất lượng

**User story:** Là nhóm phát triển, tôi muốn đo được chất lượng và chi phí để chỉnh prompt, ngưỡng và model có căn cứ.

1. THE SYSTEM SHALL ghi vết tổng hợp mỗi lượt (R10.4) và cho phép tra theo `trace_id`.
2. THE SYSTEM SHALL cung cấp bộ đánh giá (40–60 câu) gồm các nhóm: có đáp án + điều khoản đúng, cần ngữ cảnh cá nhân, đòi quyết định, không có căn cứ, văn bản hết/chưa hiệu lực, đối kháng.
3. WHEN chạy `make agent-eval` THEN THE SYSTEM SHALL báo: tỉ lệ trích đúng điều khoản, tỉ lệ từ chối đúng câu đối kháng, số lần có cam kết kết quả, số lần có tool ghi được gọi, độ trễ và token trung bình.
4. THE SYSTEM SHALL đặt mục tiêu: trích đúng ≥ 90%, từ chối đối kháng 100%, tool ghi / đổi trạng thái = 0.
5. THE SYSTEM SHALL cho phép chỉnh ngưỡng τ của `no_match` dựa trên kết quả đánh giá.

_Truy vết: 11.2 (chỉ số thành công), NF1_

### Requirement 15 — Giao diện chat (FE)

**User story:** Là sinh viên, tôi muốn một màn hình chat dễ dùng, thấy nguồn trích dẫn và biết khi nào AI không khả dụng.

1. THE SYSTEM SHALL có màn hình chat: lấy ticket, mở WebSocket, gửi `auth` rồi `ask`; tự nối lại khi rớt; nút dừng gửi `cancel`.
2. THE SYSTEM SHALL hiển thị tiến trình (`status`, `tool_call`) và stream `token` thành câu trả lời.
3. THE SYSTEM SHALL hiển thị `citations` bấm được để xem nguyên văn đoạn trích; hiển thị cảnh báo khi căn cứ là văn bản mẫu và khi `degraded=true`.
4. THE SYSTEM SHALL chỉ gọi BE (cùng origin hoặc `NEXT_PUBLIC_BE_WS_URL`), không gọi agent trực tiếp.
5. THE SYSTEM SHALL hiển thị rõ các lỗi `rate_limited`, `busy`, `timeout`, `llm_unavailable`.

_Truy vết: B7, B8_

### Requirement 16 — Môi trường dev: người dùng mặc định và dữ liệu giả

**User story:** Là lập trình viên, tôi muốn phát triển và thử trợ lý khi chưa có đăng nhập và chưa có luồng nghiệp vụ thật.

1. WHERE `APP_ENV != production` và cấu hình `AGENT_DEV_DEFAULT_USER_EMAIL` có giá trị THE SYSTEM SHALL dùng người dùng tương ứng trong `app_user` làm chủ thể khi request tool không có agent-token, và cho `ws-ticket` khi chưa có phiên đăng nhập.
2. THE SYSTEM SHALL chọn người mặc định hoàn toàn ở BE; agent và LLM SHALL NOT truyền hay đổi được.
3. IF `AGENT_DEV_DEFAULT_USER_EMAIL` được đặt khi `APP_ENV=production` THEN THE SYSTEM SHALL từ chối khởi động.
4. WHEN dùng người dùng mặc định THEN THE SYSTEM SHALL ghi audit với `reason='dev-default-user'`.
5. THE SYSTEM SHALL có lệnh `make seed-dev` tạo dữ liệu giả (1 QTV, 1 GV, ≥ 2 SV ở trạng thái khác nhau với mốc/nhật ký/minh chứng, bộ quy chế mẫu), chạy lại được, và từ chối chạy khi `APP_ENV=production`.
6. THE SYSTEM SHALL đặt dữ liệu giả **ngoài** migration; migration chỉ chứa schema.
7. WHERE đã có đăng nhập thật THE SYSTEM SHALL bỏ nhánh người dùng mặc định mà không phải sửa tool.

_Truy vết: D9 (tạm hoãn), D6_

### Requirement 17 — Prompt và cấu hình

**User story:** Là nhóm phát triển, tôi muốn sửa prompt mà không đụng code và không còn dấu vết dự án cũ.

1. THE SYSTEM SHALL đặt prompt ở `agent/prompts/*.md`: `policy_assistant.system.md`, `citation_rules.md`, `safeguards.md`, `refusals.md`; thay `{{placeholder}}` (`today`, `user_role`, `school_name`, `sample_notice`, `citation_rules`, `safeguards`, `refusals`).
2. THE SYSTEM SHALL xóa/viết lại ba prompt cũ của dự án trước ("AI20K Agent", cảnh báo y tế, `src/agents/prompts.py`).
3. THE SYSTEM SHALL cho cấu hình model, nhiệt độ, trần token, giới hạn vòng/thời gian, model embedding qua biến môi trường (`OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, …); mặc định nhiệt độ cho trợ lý chính sách thấp (≈ 0.2).
4. WHERE model là loại suy luận THE SYSTEM SHALL không gửi tham số mà model từ chối (ví dụ `temperature`) và SHALL dành đủ trần token cho cả token suy luận.
5. THE SYSTEM SHALL nạp prompt qua một bộ nạp có cache và báo lỗi rõ khi thiếu placeholder.

_Truy vết: C7 (CLAUDE.md), D10_

---

## 5. Yêu cầu phi chức năng

| Mã | Yêu cầu |
|---|---|
| NF1 | Câu trả lời đầu tiên (khung `token`) xuất hiện trong p95 ≤ 5 giây khi có LLM; có hiển thị tiến trình trong lúc chờ |
| NF2 | ≥ 200 người dùng đồng thời mà không suy giảm đáng kể (MVP: một tiến trình BE, trạng thái trong RAM, ghi chú giới hạn) |
| NF3 | Truyền tải qua HTTPS/WSS ở môi trường thật; không có khóa/token trong log |
| NF4 | Test của agent chạy được **không cần mạng và không cần khóa LLM** (LLM giả, BE giả) |
| NF5 | Giao diện tiếng Việt, dùng được trên máy tính và điện thoại |

## 6. Rủi ro và câu hỏi mở

| Mã | Vấn đề | Xử lý đề xuất |
|---|---|---|
| Q1 | Model chính: dùng model suy luận nào, ngân sách độ trễ/chi phí? | Cấu hình qua `OPENAI_MODEL`; chốt khi có kết quả đánh giá |
| Q2 | Thời hạn lưu hội thoại (Q6 nghiệp vụ) và quyền xóa của người dùng | Chờ pháp chế; bản này lưu không hạn, có ghi chú |
| Q3 | Định dạng văn bản quy định thật (DOCX/PDF/MD) | Bản này chỉ MD/text; chốt trước khi làm bộ nạp DOCX/PDF |
| Q4 | Định dạng mã sinh viên để che PII | Dùng mẫu cấu hình được, chốt khi có định dạng thật |
| Q5 | `rewrites` của Next có chuyển tiếp WebSocket không | Kiểm ở giai đoạn FE; dự phòng `NEXT_PUBLIC_BE_WS_URL` + kiểm `Origin` |
| R1 | Quy chế chỉ là bản mẫu (D6) | `is_sample` + cảnh báo; chặn go-live tới khi có quy chế thật |
| R2 | Gửi dữ liệu ra LLM ngoài | R11 + pháp chế xác nhận |
| R3 | Proxy dự phòng có thể không hỗ trợ tool/stream/embedding | R12.4 |
