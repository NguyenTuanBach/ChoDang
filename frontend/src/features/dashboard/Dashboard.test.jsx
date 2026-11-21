import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import Dashboard from "./Dashboard";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
let role = "admin";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role } }) }));

const req = (over = {}) => ({ total: 3, open: 1, approved: 1, rejected: 1, cancelled: 0, avg_decision_days: 1.5, ...over });
const data = (over = {}) => ({
  as_of: "2027-02-10", scope: "all",
  kpis: { internships: 6, in_progress: 3, completed: 1, flagged_internships: 2, overdue_internships: 1, milestone_completion_pct: 45, completion_pct: 25 },
  internship_status: [{ status: "in_progress", count: 3 }, { status: "completed", count: 1 }, { status: "draft", count: 0 }],
  milestones: [
    { code: "tiep_nhan", name: "Giấy tiếp nhận", ordinal: 0, accepted: 3, submitted: 1, pending: 0, overdue: 1, rejected: 0, total: 5, accepted_pct: 60 },
  ],
  risk: {
    open_flags: 4,
    by_severity: [{ severity: "critical", count: 1 }, { severity: "warning", count: 3 }, { severity: "info", count: 0 }],
    by_type: [{ type: "overdue", count: 2 }, { type: "log_missing", count: 2 }],
    at_risk_students: [{ internship_id: 7, student: "Lê Văn Cường", student_code: "SV003", open_flags: 2, max_severity: "critical", top_reason: "Mốc quá hạn 18 ngày" }],
  },
  requests: { extensions: req(), exceptions: req({ total: 2, avg_decision_days: null }), exceptions_by_kind: [{ kind: "credit_recognition", count: 2 }] },
  logs: { total: 10, accepted: 6, returned: 2, pending: 2, accepted_pct: 75, avg_hours_per_week: 31.5 },
  lecturers: [{ lecturer_id: 1, name: "TS. Trần", students: 3, pending_reviews: 5, open_flags: 2 }],
  programs: [{ program: "Công nghệ thông tin", internships: 6, completed: 1, milestone_pct: 45 }],
  ...over,
});

const setup = (d = data()) => {
  api.mockResolvedValue(d);
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
};

beforeEach(() => {
  api.mockReset();
  role = "admin";
});

describe("Dashboard", () => {
  it("gọi /dashboard và hiện chỉ số chính", async () => {
    setup();
    const kpis = await screen.findByRole("list", { name: "Chỉ số chính" });
    expect(api).toHaveBeenCalledWith("GET", "/dashboard");
    expect(within(kpis).getByText("Tổng hồ sơ").previousSibling).toHaveTextContent("6");
    expect(within(kpis).getByText("Mốc đã hoàn thành").previousSibling).toHaveTextContent("45%");
    expect(within(kpis).getByText("Hồ sơ có mốc quá hạn").previousSibling).toHaveTextContent("1");
  });

  it("tiêu đề theo phạm vi và ngày số liệu (QTV: toàn khóa, GV: sinh viên phụ trách)", async () => {
    setup();
    expect(await screen.findByText(/Toàn khóa · số liệu tính đến 10\/02\/2027/)).toBeInTheDocument();
  });

  it("GV thấy phạm vi sinh viên được phân công", async () => {
    role = "lecturer";
    setup();
    expect(await screen.findByText(/Sinh viên bạn phụ trách/)).toBeInTheDocument();
  });

  it("biểu đồ trạng thái bỏ nhóm 0 hồ sơ và dùng nhãn tiếng Việt", async () => {
    setup();
    const card = (await screen.findByRole("heading", { name: "Hồ sơ theo trạng thái" })).closest("section");
    expect(within(card).getByText("Đang thực tập")).toBeInTheDocument();
    expect(within(card).getByText("Hoàn thành")).toBeInTheDocument();
    expect(within(card).queryByText("Nháp")).not.toBeInTheDocument();
  });

  it("thanh tiến độ mốc có nhãn chữ và số lượng, không chỉ dựa vào màu", async () => {
    setup();
    const bar = await screen.findByRole("img", { name: /Đã chấp nhận: 3.*Quá hạn: 1/ });
    expect(bar).toHaveTextContent("3");
    expect(screen.getByText("60% đã chấp nhận · 5 hồ sơ")).toBeInTheDocument();
  });

  it("rủi ro: mức độ, loại cảnh báo và sinh viên rủi ro có liên kết tới hồ sơ", async () => {
    setup();
    expect(await screen.findByText("Mốc quá hạn", { selector: ".bar-row__label" })).toBeInTheDocument();
    expect(screen.getByText("Thiếu nhật ký tuần")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Lê Văn Cường" });
    expect(link).toHaveAttribute("href", "/internship/7");
    expect(screen.getByText("Mốc quá hạn 18 ngày")).toBeInTheDocument();
  });

  it("mọi mã luật giám sát trong cấu hình đều có nhãn tiếng Việt (không lộ mã thô)", async () => {
    setup(data({ risk: { ...data().risk, by_type: ["overdue", "due_soon", "missing_evidence", "low_hours", "log_missing"]
      .map((type, n) => ({ type, count: n + 1 })) } }));
    const card = (await screen.findByRole("heading", { name: "Rủi ro & cảnh báo" })).closest("section");
    for (const text of ["Mốc quá hạn", "Sắp đến hạn", "Thiếu minh chứng", "Thiếu giờ thực tập", "Thiếu nhật ký tuần"]) {
      expect(within(card).getByText(text, { selector: ".bar-row__label" })).toBeInTheDocument();
    }
    expect(within(card).queryByText(/low_hours|missing_evidence/)).not.toBeInTheDocument();
  });

  it("gia hạn & ngoại lệ: thời gian xử lý thiếu dữ liệu hiện gạch ngang", async () => {
    setup();
    const row = (await screen.findByRole("row", { name: /Ngoại lệ/ }));
    expect(within(row).getByText("—")).toBeInTheDocument();
    expect(screen.getByText("Công nhận tín chỉ")).toBeInTheDocument();
  });

  it("không có cảnh báo mở thì báo rõ thay vì vẽ bảng rỗng", async () => {
    setup(data({ risk: { open_flags: 0, by_severity: [], by_type: [], at_risk_students: [] } }));
    expect(await screen.findByText("Không có cảnh báo nào đang mở.")).toBeInTheDocument();
  });

  it("chưa có hồ sơ nào: hiện trạng thái trống", async () => {
    setup(data({ kpis: { ...data().kpis, internships: 0 } }));
    expect(await screen.findByText("Chưa có hồ sơ thực tập nào để thống kê.")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Chỉ số chính" })).not.toBeInTheDocument();
  });

  it("lỗi tải số liệu hiện thông báo lỗi", async () => {
    api.mockRejectedValue(new Error("Không tải được thống kê"));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText("Không tải được thống kê")).toBeInTheDocument();
  });
});
