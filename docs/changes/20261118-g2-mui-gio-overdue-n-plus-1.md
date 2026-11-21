# Nhóm 2 — Múi giờ, overdue tức thì, bỏ N+1, sửa lỗi nhỏ

> Ngày: 2026-11-18 · Branch `feature/g2-tz-overdue-perf` · Phạm vi: F4, F7, F8, F9, F10 (xem `docs/20261117-phan-cong-3-nhom.md`).

## Vấn đề

1. **Múi giờ (OQ-9).** Container chạy UTC: `date.today()` lệch 1 ngày từ 0h đến 7h sáng giờ VN, job "07:00" thực chất chạy lúc 14:00 giờ VN.
2. **Overdue trễ khoảng 24h.** Chỉ job hằng ngày mới chuyển mốc sang `overdue`. Trong khi đó monitor chạy theo sự kiện đã tạo cờ `overdue`, nên mốc vẫn hiện `pending` và UI lệch với cờ.
3. **N+1.** `run_all` lazy-load milestones, evidence, logs, student cho từng hồ sơ, và chạy 1 query "dismissed" cho mỗi finding. `GET /risk-flags` phát 2 query cho mỗi cờ. Các list mốc, nhật ký, gia hạn cũng bị như vậy.
4. **Lỗi nhỏ.**
   - Quy chế Điều 10 Khoản 2 ("gửi trước hoặc chậm nhất 3 ngày sau thời hạn") chưa được thực thi.
   - Template mốc nhận cả loại minh chứng không tồn tại.
   - `/files/{id}` trả 500 khi file trên đĩa bị mất.
   - Vẫn đính kèm được vào nhật ký đã duyệt, và không ghi audit.
   - `read-all` cập nhật từng dòng.
   - Đổi phân công GV không báo cho ai.

## Đã làm

| Việc | File |
|---|---|
| Thêm setting `APP_TIMEZONE` (mặc định `Asia/Ho_Chi_Minh`). Module `clock`: `today()`, `now()`, `local_midnight_utc()`. Thêm `tzdata` vào requirements | `src/config.py`, `src/core/clock.py` (mới), `requirements.txt` |
| Thay `date.today()` bằng `clock.today()` ở mọi chỗ của nhóm 2, cùng `milestone_out` và `seed_demo` | `monitor.py`, `monitor_routes.py`, `summary_routes.py`, `progress_routes.py`, `serializers.py`, `seed.py` |
| `lifecycle.mark_overdue()`: chuyển mốc sang overdue ngay trong `run_for`, tức là sau mỗi sự kiện, chạy trên milestones đã nạp sẵn | `src/services/lifecycle.py`, `src/services/monitor.py` |
| Scheduler: chạy `run_status` (chỉ chuyển trạng thái) lúc **00:05** giờ trường, và `run_all` (tạo cờ, gửi thông báo) lúc `MONITOR_HOUR`. Hàm `next_run()` là hàm thuần, có test riêng | `src/services/monitor.py` |
| `run_all`: eager-load toàn bộ dữ liệu, nạp cờ mở và cờ bị bác bỏ một lần cho cả lô. `run_for` nhận thêm `open_flags`/`dismissed` (tùy chọn). Bỏ `_recently_dismissed`; thay bằng `_dismissed_keys`, so sánh `closed_at` với nửa đêm giờ trường đã đổi sang UTC | `src/services/monitor.py` |
| `/risk-flags`, `/internships/{id}/milestones`, `/logs`, `/extensions`: dùng `selectinload`/`joinedload` | `monitor_routes.py`, `progress_routes.py` |
| Summary: lọc `program` bằng SQL. `q`/`risk`/sort vẫn lọc trong Python, vì `lower()` của SQLite không xử lý chữ có dấu và vì cần % mốc đã tính sẵn | `summary_routes.py` |
| Gia hạn: thực thi Điều 10 Khoản 2, tức là chậm nhất `request_grace_days` (3) ngày sau hạn mốc, nếu không thì trả 422 kèm citation và hướng SV liên hệ GV để xử lý ngoại lệ (HITL) | `progress_routes.py`, `config/cohort.yaml` |
| Template mốc: trả 422 nếu `required_evidence` không có trong `evidence_types`, hoặc nếu có hơn 1 mốc `linked_to: outline` | `admin_routes.py` |
| `/files/{id}` trả 404 khi file không còn trên đĩa. Nhật ký đã `accepted` thì trả 409 khi đính kèm, kèm audit `attachment_uploaded` | `progress_routes.py` |
| `read-all` dùng một lệnh `UPDATE`. `admin/assign` gửi thông báo `assignment` cho SV và GV mới | `monitor_routes.py`, `admin_routes.py` |

**Không làm "giới hạn số lần gia hạn".** Quy chế QĐ-TT/2026 Điều 10 không có quy định này; thêm vào là bịa luật, trái ràng buộc phải trích dẫn đúng văn bản.

## Cách kiểm tra

```powershell
docker compose run --rm --no-deps -T -v "${PWD}/src:/app/src" -v "${PWD}/tests:/app/tests" -v "${PWD}/config:/app/config" backend sh -c "python -m pytest tests/ -q; ruff check src tests"
```

- Kết quả: **186 passed** (177 test cũ cộng 9 test mới trong `tests/test_vin15/test_progress_opt.py`), ruff sạch.
- `test_query_count_does_not_grow_with_internships`: số query của `run_all`, `build_rows`, `list_flags` không đổi khi thêm 30 hồ sơ. Đã chạy test này với code cũ để chắc nó bắt được lỗi: `run_all` tăng 22 → 112 query, `/risk-flags` tăng 9 → 69.
- Lưu ý: image backend **build cứng code** vào, không mount. Muốn server chạy code mới thì `docker compose up -d --build backend`.

## Chưa kiểm tra / lưu ý

- **Chưa chạy trên Postgres.** Test tự động dùng SQLite. Cần rebuild backend rồi chạy lại mục 3–7 của `test-nhom2/HUONG-DAN-TEST-NHOM2.md`, nhất là `read-all` (`rowcount`) và query cờ "dismissed".
- **Chưa load test** với dữ liệu lớn: mới chứng minh số query là hằng số. Summary vẫn nạp toàn bộ hồ sơ trong phạm vi rồi mới phân trang; nếu có từ hàng nghìn hồ sơ trở lên thì cần tính sẵn % mốc và số cờ trong SQL.
- **Seed demo**: gia hạn #1 của sv04 được tạo thẳng trong DB cho mốc đã quá hạn khoảng 13 ngày. Qua API thì yêu cầu này giờ sẽ bị chặn theo Điều 10 Khoản 2. Dữ liệu demo vẫn để nguyên.
- **File của nhóm khác vẫn dùng `date.today()`**: `internship_routes.py` (nhóm 1, chỗ chuyển hồ sơ sang `in_progress` khi duyệt), `assistant_routes.py` (nhóm 3). Nên chuyển sang `clock.today()`.
- **File dùng chung đã sửa**, cần reviewer nhóm khác: `src/config.py`, `src/seed.py`, `src/api/vin15/serializers.py`.
- **Frontend**: không cần sửa. Lỗi 422 mới hiện đúng nhờ `errorText()` (`frontend/src/lib/api.js`), hiển thị cả message và citation. Chưa mở UI để xác nhận bằng mắt; chưa có test React.
