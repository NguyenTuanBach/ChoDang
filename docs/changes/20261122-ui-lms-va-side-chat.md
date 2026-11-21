# UI kiểu LMS (shadcn/ui) và ngăn Trợ lý (side chat) có điều hướng bằng lời

## Vấn đề
- FE là thanh menu ngang và **mỗi trang tự bọc `AuthGate`** (28 trang), nên khung bị dựng lại khi chuyển trang: không thể có ngăn chat sống qua các trang.
- Trợ lý là trang riêng `/assistant`; sinh viên phải rời trang đang làm mới hỏi được. Giao diện chưa giống một LMS.

## Đã làm
**Nền tảng giao diện (`fe/`)**
- shadcn/ui (Radix, preset Nova) + lucide-react + next-themes; `components.json`, `src/components/ui/*` (sinh bởi CLI), `src/lib/utils.ts` (`cn` = clsx + tailwind-merge).
- `globals.css`: bảng màu LMS (chàm, sidebar xanh đậm, nền xám lạnh), token `success/warning/info`, chế độ sáng/tối bằng class `.dark`. Font Inter (có bộ ký tự tiếng Việt).
- Các class cũ (`text-muted`, `bg-soft`, `bg-bg`, `text-fg`, `bg-surface`) đổi sang token shadcn trong toàn bộ TSX.
- `components/ui/ui.tsx` viết lại trên shadcn, **giữ nguyên API** (28 trang không phải sửa); thêm `PageHeader`, `StatCard`, `EmptyState`.

**Khung dùng chung**
- Route group `src/app/(app)/` (URL không đổi) với `layout.tsx` = `AuthProvider` → `AssistantProvider` → `AppShell`; layout theo vai trò (`student|lecturer|admin|dashboard`) dùng `RoleGuard`.
- `AuthGate` tách thành `AuthProvider` (phiên, thông báo chưa đọc, `useSession`) và `RoleGuard`.
- `components/shell/*`: `AppSidebar` (nhóm mục, thu gọn icon, Sheet trên di động), `SiteHeader` (breadcrumb, chuông, nút Trợ lý), `UserMenu` (đổi giao diện, đăng xuất).
- `lib/nav.ts`: mỗi mục có `key` (dùng cho trợ lý), `icon`, `group`; `pageHref`, `findCurrent`, `groupNav`.

**Ngăn Trợ lý**
- `AssistantProvider` giữ **một** phiên chat (một WebSocket) cho cả khung; `AssistantDock` (cột cố định ≥ 1024px, Sheet trên màn hình nhỏ, nút nổi, `Ctrl/Cmd+J`); `AssistantPanel`, `ChatThread`, `Composer`; `/assistant` toàn màn hình dùng chung phiên. `assistant.module.css` được xóa (viết lại bằng Tailwind).

**Điều hướng bằng lời**
- Agent: tool `navigate_to` (`policy_assistant/tools/navigate.py`), danh mục trang theo vai trò ở `policy_assistant/pages.json`; chỉ ghi một *hành động giao diện* vào `TurnContext.actions` (tối đa một trang mỗi lượt), vào `final.actions`; không có khi bị từ chối/suy giảm. Prompt persona có mục "mở trang".
- BE: `valid_actions()` trong `assistant_orchestrator` chỉ chuyển tiếp tối đa một điều hướng hợp lệ, không lưu DB. Hợp đồng ghi ở `.kiro/specs/agent-hoi-dap/contract.md`.
- FE: provider thực thi `router.push` một lần cho lượt đang chạy (không chạy khi tải lại lịch sử), URL do FE suy ra từ `NAV` theo vai trò, khóa lạ bị bỏ qua; chip "Đã mở: …" dưới câu trả lời.

**Trang chủ và đăng nhập**
- Sinh viên: lời chào, hành trình, KPI, việc cần làm, timeline mốc, ô hỏi nhanh Trợ lý. Giảng viên/quản trị: KPI từ `/api/dashboard`, hàng chờ ưu tiên, phân bố hồ sơ theo trạng thái. Dashboard dùng `StatCard`. Đăng nhập bố cục hai nửa.

## Cách kiểm tra
- `cd fe && npx tsc --noEmit && npx eslint src && npx vitest run && npm run build`.
- `cd agent && uv run pytest && uv run ruff check src tests`; `cd be && uv run pytest tests --ignore=tests/integration --ignore=tests/e2e`.
- Test mới: `AuthProvider.test.tsx` (provider + RoleGuard), `AssistantProvider.test.tsx` (điều hướng một lần, khóa lạ bị bỏ qua, Ctrl+J, câu hỏi gợi ý), `nav.test.ts` (khóa `pages.json` ↔ `nav.ts`), agent `test_policy_assistant.py` (navigate_to), BE `test_assistant_orchestrator.py` (lọc `actions`).

## Chưa kiểm tra / lưu ý
- **Chưa mở trên trình duyệt thật**: bố cục, chế độ tối, di động, việc chat giữ nguyên khi chuyển trang mới được kiểm bằng test đơn vị, chưa bằng mắt.
- Chưa thử LLM thật cho câu "mở trang …" (có gọi đúng `navigate_to` không). BE và agent đang chạy cần restart để có tool mới.
- BE: 6 test cũ trong `tests/presentation/test_agent_tools.py` (gọi `me/credit-checklist`) vẫn fail vì dịch vụ tín chỉ cần LMS/database khi dựng container — có từ trước đợt này.
- Chưa làm: tìm kiếm toàn cục, truyền "trang đang xem" cho agent, thiết kế lại bố cục từng trang con (wizard hồ sơ, duyệt hai cột), chặn điều hướng khi form đang sửa dở.
