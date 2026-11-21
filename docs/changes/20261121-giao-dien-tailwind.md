# Giao diện cơ bản bằng Tailwind (2026-11-21)

## Mục tiêu
Giao diện cũ dùng CSS Modules, menu phẳng (SV có 9 mục), trang chủ chỉ là bảng nên khó biết đang ở bước nào và phải làm gì tiếp.
Đợt này dựng lớp giao diện cơ bản, dễ dùng cho **toàn bộ** trang; không đổi API hay nghiệp vụ. Thiết kế đầy đủ ở `docs/thiet-ke-screen-flow.md`.

## Đã làm
- Cài Tailwind v4 (`tailwindcss`, `@tailwindcss/postcss`, `fe/postcss.config.mjs`); `globals.css` giữ biến màu cũ (cho `assistant.module.css`), ánh xạ sang màu Tailwind (`@theme inline`), và đặt kiểu nền cho `input/select/textarea/button/a/h1/h2` để thẻ thô vẫn đẹp. Chế độ tối vẫn theo `prefers-color-scheme`.
- Viết lại `components/ui/ui.tsx` bằng Tailwind (giữ tên và props nên các trang không phải sửa); thêm `Stepper` (thanh hành trình) và `LinkButton`; thêm tông "action" (cam) và bảng màu trạng thái thống nhất.
- `AuthGate`: thanh trên cố định, mục menu đang chọn được tô nổi, chuông thông báo có số, menu thu vào nút ☰ trên điện thoại. `usePathname` nằm trong `<Suspense>` (Next 16 bắt buộc với route động, nếu không `next build` lỗi).
- `LoginPanel`: thẻ đăng nhập căn giữa, tài khoản dev nhóm theo vai trò.
- `StudentHome`: thanh hành trình 5 bước (`lib/journey.ts`, có test), thẻ "Việc cần làm" với một nút chính, mốc cần làm.
- `QueuePanel`: danh sách thẻ, dải màu theo mức ưu tiên.
- Xóa `ui.module.css`, `auth.module.css`. Test `AuthGate.test.tsx` thêm `usePathname` vào mock.

## Cách kiểm tra
`cd fe && npx tsc --noEmit && npm run lint && npx vitest run && npm run build`, rồi mở `http://localhost:3000/login` đăng nhập dev từng vai trò. Dev server cần khởi động lại khi mới thêm `postcss.config.mjs`.

## Đã kiểm / chưa kiểm
- Đã kiểm: `tsc`, lint (0 lỗi), vitest 74/74, `next build` đạt; chụp màn hình bằng Chrome headless: đăng nhập, Tổng quan SV A (máy tính và điện thoại 390px), Hàng chờ GV, Quy định QTV.
- **Chưa kiểm bằng mắt**: các trang còn lại (hồ sơ, đề cương, mốc, nhật ký, yêu cầu, tín chỉ, chi tiết hồ sơ GV, cấu hình, LMS, audit, dashboard, thông báo) và chế độ tối. Các trang này dùng bộ `ui.tsx` mới nên nhiều khả năng ổn nhưng cần rà.
- Chưa làm (để đợt sau): wizard hồ sơ, "Hôm nay" hai cột duyệt tại chỗ, không gian một sinh viên có tab, ngăn Trợ lý nổi, gộp menu về tối đa 5 mục (menu SV/QTV hiện xuống hai dòng trên màn rộng).
- Trang Trợ lý (`assistant.module.css`) giữ nguyên.
