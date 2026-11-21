import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import InternshipDetail from "./InternshipDetail";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

let mockRole = "lecturer";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role: mockRole } }) }));

const milestone = (over = {}) => ({ id: 5, name: "Báo cáo giữa kỳ", status: "submitted", due_date: "2027-02-01", evidence: [], linked_to: null, ...over });
const log = (over = {}) => ({ id: 20, week_no: 1, content: "Làm API đăng nhập", hours: 20, review_status: "pending", comment: null, difficulties: null, ...over });

const DATA = {
  i: {
    id: 3, status: "in_progress", company_name: "Công ty Sao Mai", position: "Backend", start_date: "2027-01-05", end_date: "2027-03-30",
    student: { full_name: "Nguyễn Văn An" },
    milestones: [milestone({ evidence: [{ id: 8, filename: "bao-cao.pdf" }] })],
    outline: { status: "approved", content: "Đề cương về backend.", reason: "Đạt yêu cầu" },
  },
  logs: [log(), log({ id: 21, week_no: 2, hours: 10, content: "Viết kiểm thử", review_status: "accepted", comment: "Tốt", difficulties: "Thiếu tài liệu" })],
  audit: [{ at: "2027-01-05T08:00:00", actor: "gv.tran", entity: "internship", entity_id: 3, action: "approved", reason: "Hợp lệ" }],
};

const setup = (data = DATA) => {
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/internships/3") return data.i;
    if (method === "GET" && path === "/internships/3/logs") return data.logs;
    if (method === "GET" && path === "/internships/3/audit") return data.audit;
    return {};
  });
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={["/students/3"]}>
        <Routes><Route path="/students/:id" element={<InternshipDetail />} /></Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
  return userEvent.setup();
};

const reads = (path) => api.mock.calls.filter((c) => c[0] === "GET" && c[1] === path).length;

beforeEach(() => {
  api.mockReset();
  mockRole = "lecturer";
});

describe("InternshipDetail — hiển thị", () => {
  it("tiêu đề, mốc, minh chứng, đề cương, tổng giờ nhật ký và lịch sử audit", async () => {
    setup();
    expect(await screen.findByRole("heading", { name: "Nguyễn Văn An" })).toBeInTheDocument();
    expect(screen.getByText(/Công ty Sao Mai · Backend/)).toBeInTheDocument();
    expect(screen.getByText("Báo cáo giữa kỳ")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "bao-cao.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Đề cương về backend.")).toBeInTheDocument();
    expect(screen.getByText("Nhận xét: Đạt yêu cầu")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nhật ký (30 giờ)" })).toBeInTheDocument();
    expect(screen.getByText("gv.tran")).toBeInTheDocument();
    expect(screen.getByText("Hợp lệ")).toBeInTheDocument();
  });

  it("chưa có nhật ký → thông báo; chưa có mốc hoặc đề cương thì không hiện mục đó", async () => {
    setup({ ...DATA, i: { ...DATA.i, milestones: [], outline: null }, logs: [] });
    expect(await screen.findByText("Chưa có nhật ký.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Các mốc" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Đề cương" })).not.toBeInTheDocument();
  });

  it("lỗi tải → hiện thông báo lỗi", async () => {
    api.mockRejectedValue(new Error("Không có quyền xem hồ sơ này"));
    render(
      <ToastProvider>
        <MemoryRouter initialEntries={["/students/3"]}>
          <Routes><Route path="/students/:id" element={<InternshipDetail />} /></Routes>
        </MemoryRouter>
      </ToastProvider>,
    );
    expect(await screen.findByText("Không có quyền xem hồ sơ này")).toBeInTheDocument();
  });
});

describe("InternshipDetail — giảng viên duyệt mốc và nhật ký", () => {
  it("chấp nhận mốc đã nộp: POST kèm nhận xét rồi tải lại", async () => {
    const user = setup();
    const row = (await screen.findByText("Báo cáo giữa kỳ")).closest("li");
    await user.type(within(row).getByLabelText("Nhận xét"), "Đạt");
    await user.click(within(row).getByRole("button", { name: "Chấp nhận" }));
    await waitFor(() => expect(reads("/internships/3")).toBe(2));
    expect(api).toHaveBeenCalledWith("POST", "/milestones/5/review", { decision: "accepted", comment: "Đạt" });
  });

  it("trả lại mốc: decision là rejected", async () => {
    const user = setup();
    const row = (await screen.findByText("Báo cáo giữa kỳ")).closest("li");
    await user.click(within(row).getByRole("button", { name: "Trả lại" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/milestones/5/review", { decision: "rejected", comment: "" }));
  });

  it("mốc gắn với đề cương (linked_to) hoặc chưa nộp thì không có nút duyệt", async () => {
    setup({ ...DATA, i: { ...DATA.i, milestones: [milestone({ linked_to: "outline" }), milestone({ id: 6, name: "Mốc cuối", status: "pending" })] } });
    await screen.findByText("Mốc cuối");
    const lis = document.querySelectorAll("li.timeline__item");
    lis.forEach((li) => expect(within(li).queryByRole("button", { name: "Chấp nhận" })).not.toBeInTheDocument());
  });

  it("nhật ký chờ duyệt: trả lại dùng decision returned; nhật ký đã duyệt hiện nhận xét của GV", async () => {
    const user = setup();
    await screen.findByText("Làm API đăng nhập");
    expect(screen.getByText("GV: Tốt")).toBeInTheDocument();
    expect(screen.getByText("Khó khăn: Thiếu tài liệu")).toBeInTheDocument();
    const pendingRow = screen.getByText("Làm API đăng nhập").closest("tr");
    await user.click(within(pendingRow).getByRole("button", { name: "Trả lại" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/logs/20/review", { decision: "returned", comment: "" }));
  });
});

describe("InternshipDetail — quản trị viên chỉ xem", () => {
  it("không có nút duyệt mốc hoặc nhật ký (duyệt thuộc giảng viên phụ trách)", async () => {
    mockRole = "admin";
    setup();
    await screen.findByText("Làm API đăng nhập");
    expect(screen.queryByRole("button", { name: "Chấp nhận" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Trả lại" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Nhận xét")).not.toBeInTheDocument();
  });
});

describe("InternshipDetail — các nhánh còn lại", () => {
  it("thiếu tên công ty/vị trí hiện dấu gạch; mốc đã chấp nhận có dấu tích; audit thiếu entity_id", async () => {
    setup({
      ...DATA,
      i: { ...DATA.i, company_name: null, position: null, milestones: [milestone({ status: "accepted" })] },
      audit: [{ at: "2027-01-05T08:00:00", actor: "he-thong", entity: "milestone", entity_id: null, action: "overdue", reason: "" }],
    });
    expect(await screen.findByText(/— · — ·/)).toBeInTheDocument();
    expect(document.querySelector(".timeline__dot svg")).not.toBeNull();
    expect(screen.getByText("milestone #")).toBeInTheDocument();
  });

  it("đề cương chưa có nhận xét thì không hiện dòng nhận xét", async () => {
    setup({ ...DATA, i: { ...DATA.i, outline: { status: "submitted", content: "Đề cương chưa có nhận xét", reason: "" } } });
    await screen.findByText("Đề cương chưa có nhận xét");
    expect(screen.queryByText(/^Nhận xét:/)).not.toBeInTheDocument();
  });

  it("lỗi khi duyệt mốc → hiện lỗi, không tải lại", async () => {
    const user = setup();
    const row = (await screen.findByText("Báo cáo giữa kỳ")).closest("li");
    api.mockImplementation(async (method, path) => { if (method === "POST") throw new Error("Mốc đã được duyệt"); return {}; });
    await user.click(within(row).getByRole("button", { name: "Chấp nhận" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Mốc đã được duyệt");
    expect(reads("/internships/3")).toBe(1);
  });
});
