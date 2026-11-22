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

## Kiểm tra
- `tsc --noEmit` và `eslint` sạch; `GET /` trả 200. Xem bằng mắt qua ảnh chụp do người dùng gửi.

## Chưa kiểm tra / lưu ý
- Chưa xem chế độ tối và bố cục mobile; chưa có test cho `LandingCta`.
- Nội dung chữ, câu hỏi đáp và 3 bài viết trên landing là bản mẫu, chưa có trang chi tiết bài viết.
- Chưa chạy `npm run lint`/`vitest` toàn bộ.
