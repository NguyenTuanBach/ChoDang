import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import StudentLogs from "./StudentLogs";

vi.mock("../../lib/api", () => ({ api: vi.fn(), formData: (o) => o }));
vi.mock("../shared/EvidenceLink", () => ({ EvidenceLink: ({ id, children }) => <a data-testid={`ev-${id}`}>{children}</a> }));

const log = (over = {}) => ({
  id: 1, week_no: 1, hours: 30, content: "Học quy trình của công ty", difficulties: "", comment: null,
  review_status: "pending", attachments: [], ...over,
});

/** `logs` có thể là mảng cố định hoặc hàm trả về mảng (để mô phỏng dữ liệu đổi sau khi ghi). */
const setup = ({ internship = { id: 3, status: "in_progress", mode: "full_time" }, logs = [], missing = { weeks: [], citation: null } } = {}) => {
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/internships") return internship ? [internship] : [];
    if (method === "GET" && path === "/internships/3/logs") return typeof logs === "function" ? logs() : logs;
    if (method === "GET" && path === "/internships/3/logs/missing") return missing;
    return {};
  });
  render(<ToastProvider><StudentLogs /></ToastProvider>);
  return userEvent.setup();
};
const posts = () => api.mock.calls.filter((c) => c[0] !== "GET");

beforeEach(() => {
  api.mockReset();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StudentLogs — điều kiện mở nhật ký", () => {
  it("chưa có hồ sơ → báo nhật ký mở sau khi hồ sơ được duyệt", async () => {
    setup({ internship: null });
    expect(await screen.findByText("Nhật ký mở sau khi hồ sơ đăng ký được duyệt.")).toBeInTheDocument();
  });

  it.each(["draft", "submitted", "revision_requested"])("hồ sơ %s chưa được ghi nhật ký", async (status) => {
    setup({ internship: { id: 3, status, mode: "full_time" } });
    expect(await screen.findByText("Nhật ký mở sau khi hồ sơ đăng ký được duyệt.")).toBeInTheDocument();
    expect(api).not.toHaveBeenCalledWith("GET", "/internships/3/logs");
  });

  it("thực tập đã hoàn thành: xem được nhưng không còn form ghi mới", async () => {
    setup({ internship: { id: 3, status: "completed", mode: "full_time" }, logs: [log()] });
    expect(await screen.findByText("Học quy trình của công ty")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ghi nhật ký" })).not.toBeInTheDocument();
  });
});

describe("StudentLogs — danh sách nhật ký", () => {
  it("cộng tổng giờ và nêu quy chế giờ/tuần theo hình thức thực tập", async () => {
    setup({ logs: [log({ id: 1, hours: 30 }), log({ id: 2, week_no: 2, hours: 12.5 })] });
    expect(await screen.findByText(/Tổng 42.5 giờ · quy chế: trung bình 32 giờ\/tuần/)).toBeInTheDocument();
  });

  it("bán thời gian thì quy chế là 16 giờ/tuần", async () => {
    setup({ internship: { id: 3, status: "in_progress", mode: "part_time" } });
    expect(await screen.findByText(/trung bình 16 giờ\/tuần/)).toBeInTheDocument();
  });

  it("chưa có nhật ký → hiện dòng trống", async () => {
    setup();
    expect(await screen.findByText("Chưa có nhật ký.")).toBeInTheDocument();
  });

  it("hiện nhận xét của GV và file đính kèm", async () => {
    setup({ logs: [log({ comment: "Cần chi tiết hơn", attachments: [{ id: 21, filename: "anh-chup.png" }] })] });
    expect(await screen.findByText("GV: Cần chi tiết hơn")).toBeInTheDocument();
    expect(screen.getByTestId("ev-21")).toHaveTextContent("anh-chup.png");
  });
});

describe("StudentLogs — nhắc ghi bù tuần bị thiếu", () => {
  it("không thiếu tuần nào thì không có banner, ô Tuần điền tuần kế tiếp", async () => {
    setup({ logs: [log({ week_no: 1 }), log({ id: 2, week_no: 2 })] });
    await screen.findByRole("button", { name: "Ghi nhật ký" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Tuần")).toHaveValue(3);
  });

  it("thiếu tuần → banner nêu các tuần, kèm căn cứ, và điền sẵn tuần sớm nhất", async () => {
    setup({ logs: [log({ week_no: 1 })], missing: { weeks: [3, 4], citation: { doc: "QĐ-TT/2026", path: "Điều 8 / Khoản 1" } } });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Bạn chưa ghi nhật ký tuần 3, 4");
    expect(alert).toHaveTextContent("Căn cứ: QĐ-TT/2026 · Điều 8 / Khoản 1");
    expect(screen.getByLabelText("Tuần")).toHaveValue(3);
  });
});

describe("StudentLogs — ghi nhật ký mới", () => {
  it("gửi tuần/giờ dạng số cùng nội dung rồi tải lại; form được đặt lại", async () => {
    let logs = [];
    const user = setup({ logs: () => logs });
    const week = await screen.findByLabelText("Tuần");
    await user.clear(week);
    await user.type(week, "1");
    await user.type(screen.getByLabelText("Số giờ"), "32");
    await user.type(screen.getByLabelText("Công việc đã làm"), "Làm quen hệ thống");
    await user.type(screen.getByLabelText("Khó khăn (nếu có)"), "Chưa có tài khoản");
    logs = [log({ content: "Làm quen hệ thống" })]; // sau khi ghi, máy chủ trả về nhật ký mới
    await user.click(screen.getByRole("button", { name: "Ghi nhật ký" }));

    await waitFor(() => expect(screen.getByLabelText("Công việc đã làm")).toHaveValue(""));
    expect(posts()[0]).toEqual(["POST", "/internships/3/logs", { week_no: 1, hours: 32, content: "Làm quen hệ thống", difficulties: "Chưa có tài khoản" }]);
    expect(screen.getByLabelText("Tuần")).toHaveValue(2);
    expect(screen.getByLabelText("Số giờ")).toHaveValue(null);
    expect(screen.getAllByText("Làm quen hệ thống").length).toBeGreaterThan(0);
  });
});

describe("StudentLogs — API lỗi", () => {
  const failWrites = (message) => {
    const base = api.getMockImplementation();
    api.mockImplementation(async (method, path, ...rest) => {
      if (method !== "GET") throw new Error(message);
      return base(method, path, ...rest);
    });
  };

  it("ghi nhật ký lỗi: hiện lỗi, giữ nguyên nội dung đã gõ", async () => {
    const user = setup();
    failWrites("Tuần này đã có nhật ký");
    await user.type(await screen.findByLabelText("Số giờ"), "20");
    await user.type(screen.getByLabelText("Công việc đã làm"), "Viết tài liệu");
    await user.click(screen.getByRole("button", { name: "Ghi nhật ký" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Tuần này đã có nhật ký");
    expect(screen.getByLabelText("Công việc đã làm")).toHaveValue("Viết tài liệu");
    expect(screen.getByLabelText("Tuần")).toHaveValue(1);
  });

  it("đính kèm lỗi: hiện lỗi", async () => {
    setup({ logs: [log({ id: 8 })] });
    await screen.findByText("Học quy trình của công ty");
    failWrites("File quá 10 MB");
    fireEvent.change(screen.getByLabelText(/Đính kèm file/), { target: { files: [new File(["x"], "a.pdf", { type: "application/pdf" })] } });
    expect(await screen.findByRole("status")).toHaveTextContent("File quá 10 MB");
  });

  it("gửi lại lỗi: hiện lỗi", async () => {
    vi.stubGlobal("prompt", vi.fn(() => "Nội dung mới"));
    const user = setup({ logs: [log({ review_status: "returned" })] });
    await screen.findByRole("button", { name: "Sửa & gửi lại" });
    failWrites("Nhật ký đã được duyệt");
    await user.click(screen.getByRole("button", { name: "Sửa & gửi lại" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Nhật ký đã được duyệt");
  });
});

describe("StudentLogs — đính kèm và gửi lại", () => {
  it("đính kèm file vào nhật ký chưa được duyệt", async () => {
    setup({ logs: [log({ id: 8 })] });
    await screen.findByText("Học quy trình của công ty");
    const file = new File(["x"], "ghi-chu.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText(/Đính kèm file/), { target: { files: [file] } });
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/logs/8/attachments", { file }, true));
  });

  it("nhật ký đã được chấp nhận thì không thêm file được nữa", async () => {
    setup({ logs: [log({ review_status: "accepted" })] });
    await screen.findByText("Học quy trình của công ty");
    expect(screen.queryByLabelText(/Đính kèm file/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sửa & gửi lại" })).not.toBeInTheDocument();
  });

  it("chỉ nhật ký bị trả lại mới có 'Sửa & gửi lại'", async () => {
    setup({ logs: [log({ id: 1, review_status: "pending" }), log({ id: 2, week_no: 2, content: "Viết báo cáo tuần 2", review_status: "returned" })] });
    await screen.findByText("Viết báo cáo tuần 2");
    expect(screen.getAllByRole("button", { name: "Sửa & gửi lại" })).toHaveLength(1);
  });

  it("sửa & gửi lại: PATCH nội dung mới, giữ nguyên tuần/giờ/khó khăn", async () => {
    vi.stubGlobal("prompt", vi.fn(() => "Nội dung đã bổ sung"));
    const user = setup({ logs: [log({ id: 5, week_no: 4, hours: 20, difficulties: "Mạng chậm", review_status: "returned" })] });
    await user.click(await screen.findByRole("button", { name: "Sửa & gửi lại" }));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0]).toEqual(["PATCH", "/logs/5", { week_no: 4, content: "Nội dung đã bổ sung", difficulties: "Mạng chậm", hours: 20 }]);
  });

  it("hủy hộp thoại nhập nội dung thì không gửi gì", async () => {
    vi.stubGlobal("prompt", vi.fn(() => null));
    const user = setup({ logs: [log({ review_status: "returned" })] });
    await user.click(await screen.findByRole("button", { name: "Sửa & gửi lại" }));
    expect(posts()).toHaveLength(0);
  });
});
