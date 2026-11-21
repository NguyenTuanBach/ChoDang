# Dashboard phân tích chất lượng thực tập toàn khóa

## Mục tiêu
Phần nâng cao của đề bài: "dashboard phân tích chất lượng thực tập toàn khóa". Đề bài chỉ gợi ý "dashboard BI" trong mục
techstack, không chỉ định Power BI nên dashboard được làm ngay trong ứng dụng (GV/QTV xem), không thêm công cụ ngoài.

## Đã làm
- **Service** `src/services/analytics.py` (`cohort_dashboard`): chỉ đọc, không gọi AI, không ghi audit. Phạm vi theo người gọi
  (`scoped_internships`): QTV thấy toàn bộ, GV chỉ thấy sinh viên được phân công. Truy vấn cố định (không N+1).
- **API** `GET /api/v1/dashboard` (`src/api/vin15/dashboard_routes.py`), chỉ vai trò lecturer/admin; sinh viên nhận 403.
- **Số liệu**: KPI (tổng hồ sơ, đang thực tập, hoàn thành, % mốc đã chấp nhận, hồ sơ có cảnh báo, hồ sơ có mốc quá hạn);
  hồ sơ theo trạng thái; tiến độ theo từng mốc (chấp nhận/chờ duyệt/chưa nộp/quá hạn/bị trả); cảnh báo theo mức độ và loại +
  top 5 sinh viên rủi ro; gia hạn và ngoại lệ (tổng/chờ/duyệt/từ chối, số ngày xử lý trung bình, ngoại lệ theo loại);
  nhật ký tuần (tỉ lệ chấp nhận, giờ trung bình); tải công việc giảng viên; thống kê theo ngành.
- **Frontend** `frontend/src/features/dashboard/Dashboard.jsx`, route `/dashboard`, mục "Thống kê" trong menu GV và QTV.
  Biểu đồ vẽ bằng CSS (không thêm thư viện); mỗi thanh có nhãn chữ và con số, không chỉ dựa vào màu; có trạng thái trống/lỗi.

## Kiểm tra
- `pytest tests/test_vin15/test_dashboard.py` (7 test: số liệu khớp DB, phạm vi GV/QTV, sinh viên bị chặn, sắp xếp top rủi ro,
  thống kê ngoại lệ đổi khi có yêu cầu mới, chỉ đọc không ghi audit); `npx vitest run` → 358 passed; `ruff check` sạch.

## Chưa làm / lưu ý
- Chưa có lọc theo đợt/ngành/thời gian và chưa có xuất file; chưa có biểu đồ xu hướng theo thời gian (cần lưu ảnh chụp số liệu).
- "Chất lượng" hiện đo bằng tiến độ mốc, cảnh báo, thời gian xử lý và nhật ký; chưa có điểm đánh giá từ doanh nghiệp.
- Nếu cần BI ngoài (Power BI/Metabase) thì thêm endpoint xuất dữ liệu; chưa làm.
