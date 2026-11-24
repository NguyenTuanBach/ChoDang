# Landing page và đổi bảng màu

## Mục tiêu
Trang `/` trước đây chỉ chuyển hướng theo vai trò; người chưa đăng nhập không thấy giới thiệu. Đồng thời đổi giao diện sang trắng/đen với beige làm điểm nhấn.

## Đã làm
- `fe/src/app/page.tsx`: landing tĩnh theo cấu trúc appwing.us (thanh trên dính, hero + khung demo giả lập, 4 bước, 3 mục tính năng xen kẽ, "bạn vẫn kiểm soát", bài viết, FAQ bằng `<details>`, footer). Chỉ một nút "Đăng nhập" ở thanh trên.
- `fe/src/components/shared/LandingCta.tsx`: nút nhãn "Đăng nhập", nền beige chữ đen; đã đăng nhập thì tới `HOME[role]`, chưa thì `/login`.
- Xóa `HomeRedirect.tsx` (không còn dùng).
- `fe/src/app/globals.css`: nền trang trắng, chữ/nút chính đen, `card` và thanh menu (`sidebar`) beige, `accent`/`secondary` beige; màu trạng thái giữ lại.
- Viền thẻ: 2px, màu chữ ở 25% độ đậm (`border-foreground/25`) ở `Card`, `StatCard`, hàng hàng chờ, đăng nhập, Trợ lý nổi, landing; card nhỏ lồng trong card lớn nền trắng viền mỏng.
- Thanh tiến độ (`ProgressBar`, thanh phân bố ở `QueuePanel`): xanh lá = hoàn thành, đỏ = chưa hoàn thành, danh sách `DONE_STATUS` trong `ui.tsx`.

- Các trang quản trị/giảng viên: card trắng viền đen nhạt; popup Thêm/Sửa (`ui/dialog.tsx`, `ui/search-select.tsx`) cho LMS và Cấu hình; menu ba chấm cho cờ rủi ro; bộ lọc hàng chờ; biểu đồ tròn/cột (`ui/charts.tsx`) và card Rủi ro ở `/dashboard`; chi tiết hồ sơ gộp thông tin vào card đầu, minh chứng gần nhất kèm cột "Cập nhật".
- Landing: bỏ biểu tượng trên card, dải bốn mục, ảnh giao diện Trợ lý (`fe/public/landing/assistant.png`), card bốn bước viền be + số be (token `beige`, `beige-strong`).
- Tách cột ngày bắt đầu/kết thúc (danh sách hồ sơ, hiệu lực quy định), bỏ cột Neo ở Mốc mẫu.
- `/student/milestones`: dòng thời gian dọc (mốc xong xanh, mốc tiếp theo nổi bật, quá hạn viền đỏ). Chưa có "minh chứng yêu cầu"/"căn cứ điều khoản" vì BE chưa trả.
- Trang sinh viên: `/student` (giai đoạn hiện tại gộp mốc, nhắc việc, thông tin thực tập), `/student/final`, `/student/grades` (tín chỉ thực tập lên đầu), form gửi đơn gia hạn tại chỗ, lỗi hồ sơ dạng toast (`ErrorToast`), mọi ô hồ sơ đánh dấu bắt buộc.
- Trang giảng viên/quản trị: rủi ro tiến độ (menu ba chấm, lọc thời gian/gấp), yêu cầu chờ duyệt, chi tiết hồ sơ (nhật ký mỗi tuần một card, đề cương với menu ba chấm, nhận xét AI một lần xem, popup thông tin trên giấy khi bấm dòng mốc, cột Cảnh báo).
- `global_exception_handler`: tệp không còn trong kho trả 404 thay vì 500.

## Kiểm tra
- `tsc --noEmit` và `eslint` sạch; `GET /` trả 200. Xem bằng mắt qua ảnh chụp do người dùng gửi.

## Chưa kiểm tra / lưu ý
- Chưa xem chế độ tối và bố cục mobile; chưa có test cho `LandingCta`.
- Nội dung chữ, câu hỏi đáp và 3 bài viết trên landing là bản mẫu, chưa có trang chi tiết bài viết.
- Chưa chạy `npm run lint`/`vitest` toàn bộ.
