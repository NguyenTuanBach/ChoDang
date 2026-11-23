# Tải tệp quy chế lên và nút "Tạo embedding"

Ngày: 2026-11-23.

## Vấn đề

- Quản trị viên chỉ nạp được quy chế bằng cách **dán văn bản** vào `/admin/policies`; không tải được tệp Word/PDF/Markdown.
- Embedding chỉ được tạo lúc nạp (hoặc khi chạy lại `make seed-dev`). Agent lỗi/không chạy lúc nạp thì các đoạn mãi chỉ tìm bằng từ khóa,
  và trang quản trị không cho biết đoạn nào thiếu embedding.

## Đã làm

Nguyên tắc: tệp **không được lưu**, chỉ đọc chữ rồi điền vào ô "Nội dung". Quản trị viên xem/sửa (PDF hay vỡ dòng) rồi đi đúng luồng cũ
nạp → xem trước → xuất bản (HITL cho nội dung quy định giữ nguyên).

**BE**
- `service/policy/policy_file_reader.py` (mới) `read_policy_file(filename, data)`:
  - `.md/.markdown/.txt`: UTF-8 (bỏ BOM) hoặc UTF-16 có BOM; mã hóa khác thì báo lỗi.
  - `.docx`: đọc `word/document.xml` bằng `zipfile` + `xml.etree` (thư viện chuẩn); **dựng lại số tự động** theo `word/numbering.xml`
    ("Điều %1." → "Điều 3.", "%2." → "1.", "%3)" → "a)") vì bộ tách Điều/Khoản dựa vào các tiền tố này. Giới hạn 30 MB mỗi phần sau giải nén.
  - `.pdf`: `pypdf` (phụ thuộc mới, thuần Python); PDF có mật khẩu, quá 500 trang, hoặc **không có lớp chữ (bản scan)** thì từ chối (chưa có OCR).
  - Chuẩn hóa NFC (PDF tiếng Việt hay ở dạng tổ hợp), `\n`, gộp dòng trống; tối đa 500 000 ký tự (bằng giới hạn của yêu cầu nạp). Tệp tối đa 10 MB.
- `PolicyIngestService.extract()`: đọc tệp + tách thử, trả `chunk_count` hoặc `warning` (sai cấu trúc vẫn trả văn bản để sửa tay).
  `PolicyIngestService.embed_version()`: bù embedding còn thiếu cho một phiên bản (dùng lại `embed_missing`).
- `PolicyVersion.embedded_count` (đếm trong `_VERSION_SELECT` của `policy_repository.py`), có trong `PolicyVersionDto`.
- `policy_admin_controller.py` (chỉ QTV):
  - `POST /api/admin/policies/extract` (multipart `file`) → `{filename, text, chunk_count, warning}`.
  - `POST /api/admin/policies/versions/{id}/embed` → `{version, embedded_now, agent_enabled}`.

**FE** (`components/admin/PoliciesPanel.tsx`, `lib/types.ts`)
- Form "Nạp văn bản mới": ô chọn tệp → gọi `/extract`, điền "Nội dung", điền "Tên văn bản" theo tên tệp nếu đang trống, báo số đoạn tách thử hoặc lỗi cấu trúc.
- Bảng phiên bản: cột **Embedding** ("Đủ" hoặc `đã có/tổng`), nút **Tạo embedding** khi còn thiếu; báo khi BE không cấu hình agent hoặc agent vẫn lỗi.

## Test đã viết (CHƯA chạy)

- `be/tests/service/test_policy_file_reader.py`: txt (BOM, CRLF, NFC, không phải UTF-8), docx có/không đánh số tự động (khớp bộ tách đoạn),
  tệp sai/hỏng/rỗng, PDF trang trắng (không có lớp chữ), văn bản quá dài; `extract` và `embed_version` (bù đủ, không có agent, mã lạ → 404).
- `be/tests/presentation/test_policy_admin.py`: hai endpoint mới chỉ QTV, `/extract` trả văn bản / 422 khi sai định dạng / tệp quá 10 MB, `/embed`.

Đã thử tay (script nhỏ, không phải test): DOCX tự tạo có đánh số tự động đọc ra đúng "Điều 1." / "1." / "a)"; tệp `.doc`, PDF hỏng, DOCX hỏng báo lỗi đúng.
`npx tsc --noEmit` của FE chạy qua.

## Cách kiểm tra

1. `cd be && uv sync` (cài `pypdf`), `make test`, `make lint`.
2. Restart BE, đăng nhập dev vai trò quản trị viên, mở `/admin/policies`:
   - chọn một tệp `.docx`/`.pdf` quy chế thật → ô "Nội dung" được điền, báo số đoạn; sửa nếu cần → "Nạp và tách đoạn" → "Xem" kiểm Điều/Khoản → "Xuất bản";
   - tắt agent rồi nạp → cột Embedding `0/N`; bật agent → "Tạo embedding" → "Đủ".

## Chưa làm / lưu ý

- Chưa thử với PDF/DOCX quy chế thật của trường. PDF nhiều cột, có header/footer, số trang sẽ lẫn vào văn bản: phải sửa tay trước khi nạp.
- Chưa có OCR cho PDF scan; chưa đọc `.doc` (Word 97–2003).
- Chưa có nút "tạo lại toàn bộ embedding" (khi đổi mô hình embedding) — hiện chỉ bù đoạn **còn thiếu**.
- Chưa sửa/xóa được bản nháp; nạp sai thì tạo phiên bản nhãn khác.
- Gọi `/embed` chạy đồng bộ trong request (mỗi lô 64 đoạn); văn bản rất dài có thể mất vài chục giây.
