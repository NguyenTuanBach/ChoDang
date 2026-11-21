import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api, downloadFile } from "../../lib/api";
import StudentList from "./StudentList";

vi.mock("../../lib/api", () => ({ api: vi.fn(), downloadFile: vi.fn() }));
let role = "lecturer";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role } }) }));

const row = (over = {}) => ({
  id: 1, student_name: "Nguyễn Văn An", student_code: "SV001", program: "Công nghệ thông tin", company: "Công ty ABC",
  status: "in_progress", progress_pct: 40, next_milestone: "Báo cáo giữa kỳ", next_due: "2027-02-01", next_status: "pending",
  open_flags: 0, max_severity: null, lecturer: "TS. Trần", ...over,
});
const page = (items, { total = items.length, page_no = 1, size = 25 } = {}) => ({
  items, total, page: page_no, page_size: size, facets: { programs: ["Kỹ thuật phần mềm"] },
});

const summaryCalls = () => api.mock.calls.filter((c) => String(c[1]).startsWith("/internships-summary?"));
const lastQuery = () => new URLSearchParams(summaryCalls().at(-1)[1].split("?")[1]);

/** Mô phỏng máy chủ: trả `rows` và giữ đúng số trang người dùng yêu cầu. */
const setup = ({ rows = [row()], total = rows.length, users = [] } = {}) => {
  api.mockImplementation(async (_m, path) => {
    if (path.startsWith("/internships-summary?")) {
      const q = new URLSearchParams(path.split("?")[1]);
      return page(rows, { total, page_no: Number(q.get("page") || 1) });
    }
    if (path === "/admin/users") return users;
    return {};
  });
  render(<MemoryRouter><ToastProvider><StudentList /></ToastProvider></MemoryRouter>);
  return userEvent.setup();
};

beforeEach(() => {
  api.mockReset();
  downloadFile.mockReset();
  role = "lecturer";
});

describe("StudentList — hiển thị", () => {
  it("giảng viên thấy tiêu đề 'Sinh viên phụ trách' và không có cột GV", async () => {
    setup();
    expect(await screen.findByRole("heading", { name: "Sinh viên phụ trách" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Nguyễn Văn An" })).toHaveAttribute("href", "/internship/1");
    expect(screen.queryByRole("columnheader", { name: "GV" })).not.toBeInTheDocument();
    expect(api).not.toHaveBeenCalledWith("GET", "/admin/users");
  });

  it("hiện mã SV, ngành, doanh nghiệp, % mốc và mốc kế tiếp", async () => {
    setup();
    await screen.findByText("Nguyễn Văn An");
    expect(screen.getByText("SV001 · Công nghệ thông tin")).toBeInTheDocument();
    expect(screen.getByText("Công ty ABC")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText("Báo cáo giữa kỳ")).toBeInTheDocument();
  });

  it("thiếu doanh nghiệp hoặc mốc kế tiếp thì hiện dấu —", async () => {
    setup({ rows: [row({ company: "", next_milestone: null })] });
    await screen.findByText("Nguyễn Văn An");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3); // doanh nghiệp, mốc kế tiếp, cảnh báo
  });

  it("có cảnh báo mở thì hiện mức cao nhất và số lượng", async () => {
    setup({ rows: [row({ open_flags: 2, max_severity: "critical" })] });
    await screen.findByText("Nguyễn Văn An");
    const table = within(screen.getByRole("table")); // "Nghiêm trọng" cũng là một lựa chọn của bộ lọc rủi ro
    expect(table.getByText("Nghiêm trọng")).toBeInTheDocument();
    expect(table.getByText(/×2/)).toBeInTheDocument();
  });

  it("mốc quá hạn có nhãn quá hạn", async () => {
    setup({ rows: [row({ next_status: "overdue" })] });
    await screen.findByText("Nguyễn Văn An");
    expect(within(screen.getByText("Báo cáo giữa kỳ").closest("td")).getByText("Quá hạn")).toBeInTheDocument();
  });

  it("không có hồ sơ phù hợp → hiện dòng trống", async () => {
    setup({ rows: [] });
    expect(await screen.findByText("Không có hồ sơ phù hợp.")).toBeInTheDocument();
    expect(screen.getByText(/0 hồ sơ · trang 1\/1/)).toBeInTheDocument();
  });

  it("lỗi tải → hiện thông báo lỗi", async () => {
    api.mockRejectedValue(new Error("Không có quyền"));
    render(<MemoryRouter><ToastProvider><StudentList /></ToastProvider></MemoryRouter>);
    expect((await screen.findAllByText("Không có quyền")).length).toBeGreaterThan(0); // báo ở cả phần bộ lọc lẫn bảng
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("StudentList — quản trị viên", () => {
  const users = [
    { id: 1, role: "lecturer", full_name: "TS. Trần" },
    { id: 2, role: "lecturer", full_name: "TS. Lê" },
    { id: 9, role: "student", full_name: "Nguyễn Văn An" },
  ];

  it("thấy tiêu đề toàn khóa, cột GV và bộ lọc giảng viên (chỉ liệt kê giảng viên)", async () => {
    role = "admin";
    setup({ users });
    expect(await screen.findByRole("heading", { name: "Danh sách thực tập toàn khóa" })).toBeInTheDocument();
    expect(await screen.findByRole("columnheader", { name: "GV" })).toBeInTheDocument();
    const select = await screen.findByLabelText("Giảng viên");
    expect([...select.options].map((o) => o.textContent)).toEqual(["Tất cả", "TS. Trần", "TS. Lê"]);
  });

  it("lọc theo giảng viên gửi lecturer_id", async () => {
    role = "admin";
    const user = setup({ users });
    await user.selectOptions(await screen.findByLabelText("Giảng viên"), "2");
    await waitFor(() => expect(lastQuery().get("lecturer_id")).toBe("2"));
  });
});

describe("StudentList — lọc, tìm, sắp xếp", () => {
  it("lần tải đầu: sắp theo rủi ro giảm dần, trang 1, 25 dòng", async () => {
    setup();
    await screen.findByText("Nguyễn Văn An");
    const q = lastQuery();
    expect([q.get("sort"), q.get("order"), q.get("page"), q.get("page_size")]).toEqual(["risk", "desc", "1", "25"]);
    expect(q.has("status")).toBe(false); // bộ lọc rỗng không gửi lên
  });

  it("lọc trạng thái gửi status và quay về trang 1", async () => {
    const user = setup();
    await user.selectOptions(await screen.findByLabelText("Trạng thái"), "approved");
    await waitFor(() => expect(lastQuery().get("status")).toBe("approved"));
    expect(lastQuery().get("page")).toBe("1");
  });

  it("lọc mức rủi ro và ngành (gồm ngành lấy từ facets)", async () => {
    const user = setup();
    await user.selectOptions(await screen.findByLabelText("Mức rủi ro"), "any");
    await waitFor(() => expect(lastQuery().get("risk")).toBe("any"));
    const program = screen.getByLabelText("Ngành");
    expect([...program.options].map((o) => o.textContent)).toContain("Kỹ thuật phần mềm");
    await user.selectOptions(program, "Kỹ thuật phần mềm");
    await waitFor(() => expect(lastQuery().get("program")).toBe("Kỹ thuật phần mềm"));
  });

  it("tìm kiếm: nhập từ khóa rồi Enter gửi q đã cắt khoảng trắng", async () => {
    const user = setup();
    await user.type(await screen.findByLabelText(/Tìm \(tên/), "  an  {Enter}");
    await waitFor(() => expect(lastQuery().get("q")).toBe("an"));
  });

  it("bấm tiêu đề cột: lần đầu giảm dần, lần hai tăng dần, có mũi tên chỉ hướng", async () => {
    const user = setup();
    await screen.findByText("Nguyễn Văn An");
    await user.click(screen.getByRole("button", { name: /^Sinh viên/ }));
    await waitFor(() => expect([lastQuery().get("sort"), lastQuery().get("order")]).toEqual(["student", "desc"]));
    expect(await screen.findByRole("button", { name: "Sinh viên ▼" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Sinh viên/ }));
    await waitFor(() => expect(lastQuery().get("order")).toBe("asc"));
    expect(await screen.findByRole("button", { name: "Sinh viên ▲" })).toBeInTheDocument();
  });
});

describe("StudentList — phân trang", () => {
  it("trang đầu: 'Trước' bị khóa, 'Sau' mở khi còn trang", async () => {
    setup({ total: 60 });
    await screen.findByText(/60 hồ sơ · trang 1\/3/);
    expect(screen.getByRole("button", { name: "← Trước" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sau →" })).toBeEnabled();
  });

  it("bấm Sau sang trang 2 rồi Trước về trang 1", async () => {
    const user = setup({ total: 60 });
    await user.click(await screen.findByRole("button", { name: "Sau →" }));
    await screen.findByText(/trang 2\/3/);
    expect(lastQuery().get("page")).toBe("2");
    await user.click(screen.getByRole("button", { name: "← Trước" }));
    await screen.findByText(/trang 1\/3/);
  });

  it("trang cuối: 'Sau' bị khóa", async () => {
    const user = setup({ total: 30 });
    await user.click(await screen.findByRole("button", { name: "Sau →" }));
    await screen.findByText(/trang 2\/2/);
    expect(screen.getByRole("button", { name: "Sau →" })).toBeDisabled();
  });
});

describe("StudentList — xuất file", () => {
  it.each([["Xuất CSV", "csv"], ["Xuất Excel", "xlsx"]])("%s gọi downloadFile với định dạng %s, giữ bộ lọc, bỏ số trang", async (label, format) => {
    downloadFile.mockResolvedValue();
    const user = setup();
    await user.selectOptions(await screen.findByLabelText("Mức rủi ro"), "any");
    await waitFor(() => expect(lastQuery().get("risk")).toBe("any"));
    await user.click(screen.getByRole("button", { name: label }));
    await waitFor(() => expect(downloadFile).toHaveBeenCalledTimes(1));
    const [path, fallback] = downloadFile.mock.calls[0];
    const q = new URLSearchParams(path.split("?")[1]);
    expect(path.startsWith("/internships-summary/export?")).toBe(true);
    expect([q.get("format"), q.get("risk"), q.has("page")]).toEqual([format, "any", false]);
    expect(fallback).toBe(`danh-sach.${format}`);
  });

  it("xuất lỗi → báo bằng toast, không vỡ trang", async () => {
    downloadFile.mockRejectedValue(new Error("Không xuất được file (500)"));
    const user = setup();
    await user.click(await screen.findByRole("button", { name: "Xuất CSV" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Không xuất được file (500)");
  });
});
