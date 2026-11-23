import {
  Award,
  BarChart3,
  BookOpen,
  CalendarCheck,
  ClipboardList,
  FileText,
  Flag,
  FolderOpen,
  GraduationCap,
  Inbox,
  LayoutDashboard,
  LifeBuoy,
  NotebookPen,
  RefreshCw,
  ScrollText,
  Settings,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "./auth";

// `key` ổn định, được trợ lý (agent) dùng để chọn trang (`agent/.../pages.json`): đổi key phải đổi cả hai nơi (có test đối chiếu).
// `filters`: khóa query string mà trang đọc làm bộ lọc ban đầu (trợ lý mở trang kèm bộ lọc); phải khớp `filters` trong pages.json.
export type NavItem = { key: string; href: string; label: string; icon: LucideIcon; group: string; filters?: string[] };

const QUEUE_FILTERS = ["kind"];
const INTERNSHIP_FILTERS = ["status", "milestone", "milestone_status", "flagged"];

// Menu theo vai trò, chia nhóm. Trang chủ "/" chuyển người dùng về trang đầu của vai trò.
export const NAV: Record<Role, NavItem[]> = {
  student: [
    { key: "overview", href: "/student", label: "Tổng quan", icon: LayoutDashboard, group: "Chung" },
    { key: "internship", href: "/student/internship", label: "Hồ sơ", icon: FileText, group: "Thực tập" },
    { key: "outline", href: "/student/outline", label: "Đề cương", icon: ClipboardList, group: "Thực tập" },
    { key: "milestones", href: "/student/milestones", label: "Mốc & minh chứng", icon: CalendarCheck, group: "Thực tập" },
    { key: "journal", href: "/student/journal", label: "Nhật ký", icon: NotebookPen, group: "Thực tập" },
    { key: "requests", href: "/student/requests", label: "Gia hạn / ngoại lệ", icon: LifeBuoy, group: "Yêu cầu" },
    { key: "final", href: "/student/final", label: "Kết thúc & tín chỉ", icon: Award, group: "Kết quả" },
    { key: "grades", href: "/student/grades", label: "Bảng điểm", icon: GraduationCap, group: "Kết quả" },
  ],
  lecturer: [
    { key: "queue", href: "/lecturer", label: "Hàng chờ", icon: Inbox, group: "Công việc", filters: QUEUE_FILTERS },
    { key: "students", href: "/lecturer/students", label: "Sinh viên", icon: Users, group: "Công việc" },
    { key: "internships", href: "/lecturer/internships", label: "Hồ sơ", icon: FolderOpen, group: "Công việc", filters: INTERNSHIP_FILTERS },
    { key: "requests", href: "/lecturer/requests", label: "Yêu cầu", icon: LifeBuoy, group: "Công việc" },
    { key: "flags", href: "/lecturer/flags", label: "Cờ rủi ro", icon: Flag, group: "Theo dõi", filters: ["status"] },
    { key: "dashboard", href: "/dashboard", label: "Dashboard", icon: BarChart3, group: "Theo dõi" },
  ],
  admin: [
    { key: "queue", href: "/admin", label: "Hàng chờ", icon: Inbox, group: "Vận hành", filters: QUEUE_FILTERS },
    { key: "internships", href: "/admin/internships", label: "Hồ sơ", icon: FolderOpen, group: "Vận hành", filters: INTERNSHIP_FILTERS },
    { key: "requests", href: "/admin/requests", label: "Yêu cầu", icon: LifeBuoy, group: "Vận hành" },
    { key: "credit", href: "/admin/credit", label: "Tín chỉ", icon: Award, group: "Vận hành" },
    { key: "accounts", href: "/admin/lecturers", label: "Tài khoản", icon: UserCog, group: "Cấu hình" },
    { key: "config", href: "/admin/config", label: "Cấu hình", icon: Settings, group: "Cấu hình" },
    { key: "policies", href: "/admin/policies", label: "Quy định", icon: BookOpen, group: "Cấu hình" },
    { key: "lms", href: "/admin/lms", label: "LMS", icon: RefreshCw, group: "Cấu hình" },
    { key: "dashboard", href: "/dashboard", label: "Dashboard", icon: BarChart3, group: "Báo cáo" },
    { key: "audit", href: "/admin/audit", label: "Audit", icon: ScrollText, group: "Báo cáo" },
  ],
};

// Trang ngoài menu nhưng vẫn mở được (chuông thông báo, trợ lý toàn màn hình).
export const EXTRA_PAGES: { key: string; href: string; label: string }[] = [
  { key: "notifications", href: "/notifications", label: "Thông báo" },
  { key: "assistant", href: "/assistant", label: "Trợ lý" },
];

// Trang ngoài menu cần mã hồ sơ (trợ lý mở "hồ sơ của bạn An"); `pattern` nhận đường dẫn để biết người dùng đang xem hồ sơ nào.
export type DetailPage = { key: string; label: string; href: (internshipId: number) => string; pattern: RegExp };
export const DETAIL_PAGES: Record<Role, DetailPage[]> = {
  student: [],
  lecturer: [{ key: "internship_detail", label: "Chi tiết hồ sơ", href: (id) => `/lecturer/internships/${id}`, pattern: /^\/lecturer\/internships\/(\d+)\/?$/ }],
  admin: [{ key: "internship_detail", label: "Chi tiết hồ sơ", href: (id) => `/admin/internships/${id}`, pattern: /^\/admin\/internships\/(\d+)\/?$/ }],
};

export const HOME: Record<Role, string> = { student: "/student", lecturer: "/lecturer", admin: "/admin" };

export function groupNav(items: NavItem[]): { group: string; items: NavItem[] }[] {
  const groups: { group: string; items: NavItem[] }[] = [];
  for (const item of items) {
    const found = groups.find((g) => g.group === item.group);
    if (found) found.items.push(item);
    else groups.push({ group: item.group, items: [item] });
  }
  return groups;
}

// Mục đang chọn: khớp đúng đường dẫn, hoặc đường dẫn con của mục có từ 2 cấp trở lên (vd /student/outline).
export function isActive(pathname: string, href: string): boolean {
  return pathname === href || (href.split("/").length > 2 && pathname.startsWith(`${href}/`));
}

// Mục khớp dài nhất với đường dẫn hiện tại (dùng cho breadcrumb và tiêu đề).
export function findCurrent(role: Role, pathname: string): { key: string; label: string; group?: string; href: string } | null {
  const candidates = [...NAV[role], ...EXTRA_PAGES.map((p) => ({ ...p, group: undefined }))];
  const matches = candidates.filter((item) => isActive(pathname, item.href));
  matches.sort((a, b) => b.href.length - a.href.length);
  return matches[0] ? { key: matches[0].key, label: matches[0].label, group: matches[0].group, href: matches[0].href } : null;
}

// Trang người dùng đang mở, gửi kèm câu hỏi để trợ lý hiểu "trang này" (chỉ khóa + mã hồ sơ, không gửi URL).
export function currentPageRef(role: Role, pathname: string): { key: string; internship_id?: number } | null {
  for (const detail of DETAIL_PAGES[role]) {
    const match = detail.pattern.exec(pathname);
    if (match) return { key: detail.key, internship_id: Number(match[1]) };
  }
  const current = findCurrent(role, pathname);
  return current ? { key: current.key } : null;
}

export type PageTarget = { internshipId?: number | null; filters?: Record<string, string> | null };

// Trang theo khóa (do trợ lý chọn) -> đường dẫn. FE là nơi duy nhất giữ URL; khóa lạ hoặc ngoài vai trò trả null.
// Trang chi tiết cần mã hồ sơ (thiếu/sai thì null). Bộ lọc chỉ giữ khóa trang khai báo trong `filters`; khóa lạ bị bỏ.
export function pageHref(role: Role, key: string, target: PageTarget = {}): { href: string; label: string } | null {
  const detail = DETAIL_PAGES[role].find((d) => d.key === key);
  if (detail) {
    const id = target.internshipId;
    return typeof id === "number" && Number.isInteger(id) && id > 0 ? { href: detail.href(id), label: detail.label } : null;
  }
  const item: { href: string; label: string; filters?: string[] } | undefined = NAV[role].find((i) => i.key === key) ?? EXTRA_PAGES.find((p) => p.key === key);
  if (!item) return null;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(target.filters ?? {})) {
    if (item.filters?.includes(k) && typeof v === "string" && v) params.set(k, v);
  }
  const qs = params.toString();
  return { href: qs ? `${item.href}?${qs}` : item.href, label: item.label };
}
