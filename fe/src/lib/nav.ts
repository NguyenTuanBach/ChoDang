import type { Role } from "./auth";

export type NavItem = { href: string; label: string };

// Menu theo vai trò. Trang chủ "/" chuyển người dùng về trang đầu của vai trò.
export const NAV: Record<Role, NavItem[]> = {
  student: [
    { href: "/student", label: "Tổng quan" },
    { href: "/student/internship", label: "Hồ sơ" },
    { href: "/student/outline", label: "Đề cương" },
    { href: "/student/milestones", label: "Mốc & minh chứng" },
    { href: "/student/journal", label: "Nhật ký" },
    { href: "/student/requests", label: "Gia hạn / ngoại lệ" },
    { href: "/student/final", label: "Kết thúc & tín chỉ" },
    { href: "/student/grades", label: "Bảng điểm" },
    { href: "/assistant", label: "Trợ lý" },
  ],
  lecturer: [
    { href: "/lecturer", label: "Hàng chờ" },
    { href: "/lecturer/students", label: "Sinh viên" },
    { href: "/lecturer/internships", label: "Hồ sơ" },
    { href: "/lecturer/requests", label: "Yêu cầu" },
    { href: "/lecturer/flags", label: "Cờ rủi ro" },
    { href: "/dashboard", label: "Dashboard" },
    { href: "/assistant", label: "Trợ lý" },
  ],
  admin: [
    { href: "/admin", label: "Hàng chờ" },
    { href: "/admin/lecturers", label: "Tài khoản" },
    { href: "/admin/internships", label: "Hồ sơ" },
    { href: "/admin/requests", label: "Yêu cầu" },
    { href: "/admin/config", label: "Cấu hình" },
    { href: "/admin/policies", label: "Quy định" },
    { href: "/admin/lms", label: "LMS" },
    { href: "/dashboard", label: "Dashboard" },
    { href: "/admin/audit", label: "Audit" },
    { href: "/assistant", label: "Trợ lý" },
  ],
};

export const HOME: Record<Role, string> = { student: "/student", lecturer: "/lecturer", admin: "/admin" };
