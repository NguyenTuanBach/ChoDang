# Test giao diện React (Vitest) cho các màn hình của cả ba nhóm

## Vấn đề / mục tiêu
Frontend chưa có test tự động (chỉ có `dev`, `build`, `preview`). Việc 6 của nhóm 1: viết test cho các màn hình
đăng ký và duyệt. Đã dựng khung test và phủ cả 8 màn hình của nhóm 1.
Cập nhật 2026-11-19: phủ nốt các màn hình của nhóm 2 (timeline, nhật ký, gia hạn, cảnh báo, danh sách sinh viên,
quản trị, xem minh chứng, thông báo) và nhóm 3 (trợ lý, văn bản quy định, đăng nhập, `AuthContext`, `ChatContext`);
xem mục "Nhóm 2 và nhóm 3" bên dưới.

## Đã làm
- Khung test: `frontend/package.json` (devDependencies `vitest`, `jsdom`, `@testing-library/react|dom|user-event|jest-dom`,
  `@vitest/coverage-v8`; script `npm test`, `npm run test:watch`, `npm run test:coverage`), `frontend/vitest.config.js`
  (jsdom, globals), `frontend/src/test/setup.js` (jest-dom, cleanup, stub `scrollTo`/`scrollIntoView` của jsdom).
- Test (mock `api`/`streamIntake`, không cần backend), 158 test:

| Màn hình | File test | Số test | Nội dung chính |
|---|---|---|---|
| `DecisionBox` | `lecturer/DecisionBox.test.jsx` | 6 | số nút theo loại, đúng endpoint + `reason` + `version`, gia hạn không gửi version, không gọi API khi chưa bấm, API lỗi |
| `LecturerQueue` | `lecturer/LecturerQueue.test.jsx`, `LecturerQueue.sections.test.jsx` | 15 + 18 | hàng chờ trống/đếm/lỗi tải; thẻ hồ sơ, đề cương (tóm tắt AI, CĐR chưa nhắc tới, không có gợi ý), gia hạn; quyết định POST + tải lại; lỗi khi quyết định; không tự quyết. Phần nhóm 2 thêm: 3 chế độ sắp xếp (Ưu tiên, Chờ lâu nhất, Theo loại; nhớ lựa chọn, nhãn và lý do ưu tiên), chế độ Theo loại chia 5 mục có tiêu đề và số lượng, thứ tự mục, thẻ mốc đã nộp (thiếu minh chứng, file, liên kết hồ sơ, duyệt/trả lại), thẻ nhật ký tuần (khó khăn, đính kèm, `returned`/`accepted`, lỗi) |
| `InternshipDetail` | `lecturer/InternshipDetail.test.jsx` | 11 | mốc/minh chứng/đề cương/giờ nhật ký/audit; duyệt mốc và nhật ký (`accepted`/`rejected`/`returned`); mốc gắn đề cương hoặc chưa nộp không có nút duyệt; admin chỉ xem; lỗi khi duyệt |
| `RegistrationForm` | `student/RegistrationForm.test.jsx`, `RegistrationForm.more.test.jsx` | 15 + 24 | hiển thị/khóa; bảng gợi ý AI, cần nhập tay, độ tin cậy, nguồn, DN khớp; Điền vào form + dấu AI; OCR/LLM lỗi; SSE lỗi/ngắt/mạng; tiến trình; xem nguồn; lưu nháp (version, trim, null, ai_fields); kiểm tra quy chế (tô lỗi theo trường, căn cứ); nộp (thành công, vi phạm, lỗi lưu, lỗi khác) |
| `IntakeProgress` | `student/IntakeProgress.test.jsx` | 12 | bước, aria-current, OCR 4 bước, thanh tiến độ theo trang, đồng hồ, nhắc đọc file >4s, dọn timer |
| `IntakeSource` | `student/IntakeSource.test.jsx` | 15 | văn bản (tô đoạn, đoạn chồng), ảnh (khung theo %, theo trang, nhãn dùng giá trị thô), tab, active, cắt văn bản |
| `Outline` | `student/Outline.test.jsx` | 12 | nộp/nộp lại theo trạng thái, nhận xét GV, vai trò khác sinh viên chỉ xem, lỗi server |
| `StudentHome` | `student/StudentHome.test.jsx` | 30 | chưa có hồ sơ (tạo hồ sơ), việc tiếp theo (còn/quá hạn/hoàn thành), cảnh báo, rủi ro theo mức, form sửa được theo trạng thái, đề cương/gia hạn hiện theo điều kiện (con `RegistrationForm`, `Outline`, `ExtensionList`, `Timeline` được giả lập) |

- Độ phủ (`npm run test:coverage`, 8 màn hình trên): 100% dòng, 98,8% nhánh. Nhánh còn lại là vài giá trị mặc định
  (`initialValues` cho `mode`, `?.` của khung xem).

## Nhóm 2 và nhóm 3 (2026-11-19)
13 file test mới, 175 test (tổng 23 file, 333 test; số test từng file dưới đây là lúc viết lần đầu, chưa gồm các test đường lỗi thêm sau, xem mục "Cùng lỗi ở nhóm 2"). Cũng mock `api`; các khối con có test riêng được giả lập.

| Nhóm | Màn hình | File test | Số test | Nội dung chính |
|---|---|---|---|---|
| 2 | `Timeline` | `student/Timeline.test.jsx` | 19 | mốc hiện tại (`aria-current`), số ngày còn/quá hạn, minh chứng yêu cầu, ai được thao tác (sinh viên: pending/overdue/rejected; mốc gắn đề cương và giảng viên chỉ xem), tải minh chứng đúng loại, nộp mốc, form xin gia hạn (có/không kèm file) |
| 2 | `StudentLogs` | `student/StudentLogs.test.jsx` | 17 | điều kiện mở nhật ký theo trạng thái hồ sơ, tổng giờ và quy chế 32/16 giờ, banner tuần thiếu kèm căn cứ, ghi nhật ký (kiểu số, đặt lại form), đính kèm, sửa & gửi lại |
| 2 | `ExtensionList` | `student/ExtensionList.test.jsx` | 6 | hạn cũ → mới, nhận xét GV, chỉ yêu cầu đang chờ của sinh viên mới hủy được |
| 2 | `Flags` | `lecturer/Flags.test.jsx` | 9 | trống/lỗi, link hồ sơ, ba hành động (ghi nhận, đã xử lý, bác bỏ) kèm ghi chú, ghi chú độc lập từng cờ |
| 2 | `StudentList` | `lecturer/StudentList.test.jsx` | 20 | cột/bộ lọc theo vai trò, lọc trạng thái/ngành/rủi ro/giảng viên/tìm kiếm, sắp xếp, phân trang, xuất CSV/Excel giữ bộ lọc, lỗi xuất |
| 2 | `AdminHome` | `admin/AdminHome.test.jsx` | 14 | chạy giám sát, sửa/thêm/xóa/lưu mẫu mốc (chuyển chuỗi thành số/mảng/căn cứ), phân công GV, tạo tài khoản |
| 2 | `EvidencePreview`, `EvidenceLink` | `shared/EvidencePreview.test.jsx` | 19 | các loại file (PDF, ảnh, Word, hỏng, mất, không xem được), đóng bằng nút/Esc/bấm ngoài, khóa cuộn, tải về qua link ký mới, gợi ý AI chỉ cho GV/QTV (cảnh báo, checklist, CĐR chưa nhắc tới, AI lỗi) |
| 2 | `Notifications` | `layout/Notifications.test.jsx` | 9 | đếm chưa đọc, mở panel + đánh dấu đã đọc, link, trống, API lỗi |
| 3 | `Assistant` | `shared/Assistant.test.jsx` | 14 | gợi ý, gửi (cắt khoảng trắng, Enter), khóa khi đang trả lời, nguồn trích dẫn, ghi chú trích nguyên văn, link gia hạn |
| 3 | `Policies` | `shared/Policies.test.jsx` | 8 | danh sách và hiệu lực, xem điều khoản, form tải lên chỉ cho người có quyền, `supersedes_code` |
| 3 | `Login` | `auth/Login.test.jsx` | 12 | gửi/khóa/lỗi, tài khoản demo, nút SSO theo cấu hình |
| 3 | `AuthContext` | `context/AuthContext.test.jsx` | 8 | khởi động có/không token, token hỏng, 401 tự đăng xuất, chuẩn hóa tên đăng nhập, SSO, đăng xuất |
| 3 | `ChatContext` | `context/ChatContext.test.jsx` | 7 | stage/delta/done/error, giữ `conversation_id`, lỗi mạng hiện trong khung chat |

Kiểm tra độ nhạy: đổi tạm 4 chỗ trong mã nguồn (cho giảng viên thao tác ở `Timeline`, `Flags` gửi nhầm action, `Login`
không điền mật khẩu demo, `AdminHome` gửi id dạng chuỗi) thì test tương ứng đều đỏ; đã hoàn nguyên.

## Lỗi thật do test phát hiện và đã sửa
Cùng một lỗi: `run()` (ToastContext) hiện lỗi trên toast rồi ném lại; các hàm xử lý sự kiện không bắt nên thành
unhandled rejection (người dùng vẫn thấy toast, nhưng console có lỗi và có chỗ còn chạy tiếp bước sau):
- `DecisionBox.jsx` (`decide`), `Outline.jsx` (`send`), `StudentHome.jsx` (nút tạo hồ sơ), `ReviewInline.jsx`
  (`send`; nhóm 2 đã tách khỏi `InternshipDetail.jsx` sang file riêng, dùng chung với hàng chờ): nay bắt lỗi và dừng,
  không tải lại.
- `RegistrationForm.jsx`: lưu nháp, kiểm tra quy chế, nộp hồ sơ. Trước đây khi lưu lỗi, "kiểm tra" và "nộp" vẫn có thể
  chạy tiếp; nay dừng ngay sau khi lưu thất bại.

### Cùng lỗi ở nhóm 2 (2026-11-19), đã sửa
Test đường lỗi của nhóm 2 cho thấy các hàm xử lý sự kiện cũng không bắt lỗi của `run()` (unhandled rejection). Đã bọc
`try/catch` rồi dừng, không tải lại, giữ nguyên nội dung người dùng đang nhập:
- `Timeline.jsx`: `upload`, `submit`, `send` (xin gia hạn: tải minh chứng lỗi thì không gửi yêu cầu, giữ form).
- `StudentLogs.jsx`: `save`, `attach`, `resend`. `ExtensionList.jsx`: `cancel`. `Flags.jsx`: `act`.
- `AdminHome.jsx`: `runMonitor` (không báo "xong" khi lỗi), `save` (không tải lại để khỏi mất dòng đang sửa), `assign`, `submit`.
- Đã kiểm tra: với mã cũ, test mới báo Unhandled Rejection (thử với `Flags.jsx`, `Timeline.jsx`); với mã mới thì sạch.

## Cách kiểm tra
- `cd frontend && npm install && npm test`: 333 passed (23 file). `npm run build` thành công. `npm run test:coverage` để xem độ phủ
  (số liệu độ phủ ở trên chỉ tính 8 màn hình nhóm 1; chưa đo cho nhóm 2 và 3).

## Chưa kiểm tra / lưu ý
- `Policies` (tải lên): jsdom không đưa file chọn bằng `user.upload` vào `FormData` của form nên test gửi form bằng
  `fireEvent.submit` (tắt kiểm tra ràng buộc) và không khẳng định nội dung file; ràng buộc "bắt buộc chọn file" do trình duyệt xử lý.
- Chưa có test end-to-end với backend thật và trình duyệt thật; chưa kiểm vị trí khung (`boxes`) bằng output Tesseract thật
  (việc 3), test hiện dùng dữ liệu giả lập.
- `DecisionBox` chỉ ghi "nhận xét bắt buộc" ở nhãn, không chặn ở client; ràng buộc nằm ở backend. Test không khẳng định
  việc chặn ở client.
- Khi viết test: đừng `return` mock từ `beforeEach` (vitest coi hàm trả về là teardown và gọi nó).
- Đổi `package.json`/`package-lock.json` là file dùng chung → cần nhờ người nhóm khác review PR.
