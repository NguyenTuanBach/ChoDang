# Sửa nhầm chữ↔số (O/0, I/l/1) trong ngày tháng và số điện thoại

## Vấn đề
OCR hay đọc `0` thành `O` và `1` thành `l`/`I`. Trước đây chỉ mã số thuế được sửa (`_DIGIT_FIX`);
ngày tháng và số điện thoại bị bỏ sót hoặc `normalize_*` trả `None` (ví dụ `O5/Ol/2O27`).

## Đã làm (`src/services/intake.py`)
- Ngày: `_DATE`, `_DATE_WORDS`, `_DATE_ANY` nhận `[0-9oil]` thay cho `\d`; `normalize_date` đổi `o→0`, `i/l→1`
  (khớp trên bản đã chữ thường của `_fold`). Không đổi `s/b` ở ngày để tránh khớp nhầm chữ thường.
- Điện thoại:
  - `regex_extract`: số sau nhãn "điện thoại/sđt/..." nhận `[0-9oilsb]`, chặn bắt thừa chữ cái đứng sau số.
  - `normalize_phone`: chỉ đổi chữ→số (dùng `_DIGIT_FIX`) khi cả chuỗi chỉ gồm ký tự kiểu số điện thoại,
    nên tên người hay chữ khác vẫn trả `None`.
- Test mới trong `tests/test_vin15/test_intake_robust.py` (3 test).

## Kiểm tra
- `pytest tests/ -q`: 179 passed, 1 skipped (trước khi sửa: 176 passed, 1 skipped).
- `ruff check src tests`: sạch. `ruff check .` còn 8 lỗi có sẵn ngoài `src/` và `tests/`, không do thay đổi này.

## Chưa kiểm tra / lưu ý
- Số điện thoại không nhãn (nhánh dự phòng trong `regex_extract`) vẫn chỉ nhận chữ số thật, chưa sửa nhầm chữ↔số.
- Chưa đo trên bản scan thật; cần chạy `scripts/ocr_eval.py` khi có ~20 bản scan (việc 1 của nhóm 1).
