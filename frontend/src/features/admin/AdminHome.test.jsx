import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import AdminHome from "./AdminHome";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

const templates = () => [
  { code: "receipt", name: "Nộp giấy tiếp nhận", anchor: "start", offset_days: 7, required_evidence: ["receipt", "other"], linked_to: null, citation: { doc: "QĐ-TT/2026", path: "Điều 7 / Khoản 1" } },
  { code: "outline", name: "Nộp đề cương", anchor: "start", offset_days: 14, required_evidence: [], linked_to: "outline", citation: {} },
];
const users = [
  { id: 1, role: "lecturer", full_name: "TS. Trần" },
  { id: 2, role: "lecturer", full_name: "TS. Lê" },
  { id: 10, role: "student", full_name: "Nguyễn Văn An", student_code: "SV001", lecturer_id: 1 },
  { id: 11, role: "student", full_name: "Lê Thị Bình", student_code: "SV002", lecturer_id: 2 },
];

const setup = async ({ monitor = { flags_created: 2, overdue: 1 } } = {}) => {
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/admin/users") return users;
    if (method === "GET" && path === "/admin/cohort") return { name: "Học kỳ 1/2027", code: "K27-1", templates: templates() };
    if (path === "/monitor/run") return monitor;
    return {};
  });
  render(<ToastProvider><AdminHome /></ToastProvider>);
  await screen.findByRole("heading", { name: "Quản trị" });
  return userEvent.setup();
};
const writes = () => api.mock.calls.filter((c) => c[0] !== "GET");

beforeEach(() => {
  api.mockReset();
});

describe("AdminHome — tải trang", () => {
  it("hiện tên đợt và mã đợt", async () => {
    await setup();
    expect(screen.getByText("Đợt: Học kỳ 1/2027 (K27-1)")).toBeInTheDocument();
  });

  it("lỗi tải → hiện lỗi, không hiện form quản trị", async () => {
    api.mockRejectedValue(new Error("Chỉ quản trị viên được truy cập"));
    render(<ToastProvider><AdminHome /></ToastProvider>);
    expect(await screen.findByText("Chỉ quản trị viên được truy cập")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Lưu mẫu mốc" })).not.toBeInTheDocument();
  });
});

describe("AdminHome — chạy giám sát", () => {
  it("POST /monitor/run rồi báo số cảnh báo mới và mốc quá hạn", async () => {
    const user = await setup();
    await user.click(screen.getByRole("button", { name: "Chạy giám sát ngay" }));
    expect(await screen.findByText("Giám sát xong: 2 cảnh báo mới, 1 mốc quá hạn")).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("POST", "/monitor/run");
  });
});

describe("AdminHome — API lỗi", () => {
  /** Từ lúc gọi, mọi lệnh ghi (không phải GET) đều bị máy chủ từ chối. */
  const failWrites = (message) => {
    const base = api.getMockImplementation();
    api.mockImplementation(async (method, path, ...rest) => {
      if (method !== "GET") throw new Error(message);
      return base(method, path, ...rest);
    });
  };
  const cohortLoads = () => api.mock.calls.filter((c) => c[0] === "GET" && c[1] === "/admin/cohort").length;

  it("chạy giám sát lỗi: hiện lỗi và không báo 'xong'", async () => {
    const user = await setup();
    failWrites("Giám sát đang chạy");
    await user.click(screen.getByRole("button", { name: "Chạy giám sát ngay" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Giám sát đang chạy");
    expect(screen.queryByText(/Giám sát xong/)).not.toBeInTheDocument();
  });

  it("lưu mẫu mốc lỗi (vd. minh chứng không tồn tại): hiện lỗi, không tải lại, giữ các dòng đang sửa", async () => {
    const user = await setup();
    failWrites("Loại minh chứng không tồn tại");
    const name = screen.getAllByLabelText("Tên mốc")[0];
    await user.clear(name);
    await user.type(name, "Tên đang sửa");
    await user.click(screen.getByRole("button", { name: "Lưu mẫu mốc" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Loại minh chứng không tồn tại");
    expect(cohortLoads()).toBe(1);
    expect(screen.getAllByLabelText("Tên mốc")[0]).toHaveValue("Tên đang sửa");
  });

  it("phân công lỗi: hiện lỗi", async () => {
    const user = await setup();
    failWrites("Giảng viên không tồn tại");
    await user.selectOptions(screen.getByLabelText("GV phụ trách Nguyễn Văn An"), "2");
    expect(await screen.findByRole("status")).toHaveTextContent("Giảng viên không tồn tại");
  });

  it("tạo tài khoản lỗi (trùng tên): hiện lỗi và giữ nguyên nội dung form", async () => {
    const user = await setup();
    failWrites("Tên đăng nhập đã tồn tại");
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv99");
    await user.type(screen.getByLabelText("Mật khẩu"), "matkhau1");
    await user.type(screen.getByLabelText("Họ tên"), "Phạm Văn Cường");
    await user.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Tên đăng nhập đã tồn tại");
    expect(screen.getByLabelText("Tên đăng nhập")).toHaveValue("sv99");
  });
});

describe("AdminHome — mẫu mốc", () => {
  it("mỗi mẫu một dòng; mẫu gắn đề cương khóa ô minh chứng", async () => {
    await setup();
    expect(screen.getAllByLabelText("Tên mốc").map((i) => i.value)).toEqual(["Nộp giấy tiếp nhận", "Nộp đề cương"]);
    const evidence = screen.getAllByLabelText("Minh chứng yêu cầu");
    expect(evidence[0]).toHaveValue("receipt, other");
    expect(evidence[1]).toBeDisabled();
    expect(evidence[1]).toHaveAttribute("placeholder", "theo đề cương");
  });

  it("ô căn cứ hiện 'văn bản · điều khoản'", async () => {
    await setup();
    expect(screen.getAllByLabelText("Căn cứ")[0]).toHaveValue("QĐ-TT/2026 · Điều 7 / Khoản 1");
  });

  it("Thêm mốc thêm một dòng trống; ✕ xóa đúng dòng đó", async () => {
    const user = await setup();
    await user.click(screen.getByRole("button", { name: "Thêm mốc" }));
    expect(screen.getAllByLabelText("Mã")).toHaveLength(3);
    await user.click(screen.getAllByRole("button", { name: "Xóa mốc" })[0]);
    expect(screen.getAllByLabelText("Tên mốc").map((i) => i.value)).toEqual(["Nộp đề cương", ""]);
  });

  it("lưu: chuyển chuỗi nhập thành dữ liệu (số ngày là số, minh chứng là mảng, căn cứ tách thành doc/path)", async () => {
    const user = await setup();
    const name = screen.getAllByLabelText("Tên mốc")[0];
    await user.clear(name);
    await user.type(name, "Nộp giấy tiếp nhận (sửa)");
    fireEvent.change(screen.getAllByLabelText("Lệch ngày")[0], { target: { value: "10" } });
    await user.selectOptions(screen.getAllByLabelText("Mốc tính hạn")[0], "end");
    await user.click(screen.getByRole("button", { name: "Lưu mẫu mốc" }));

    await waitFor(() => expect(writes().some((c) => c[0] === "PUT")).toBe(true));
    const [, path, body] = writes().find((c) => c[0] === "PUT");
    expect(path).toBe("/admin/cohort/templates");
    expect(body[0]).toEqual({
      code: "receipt", name: "Nộp giấy tiếp nhận (sửa)", anchor: "end", offset_days: 10,
      required_evidence: ["receipt", "other"], linked_to: null, citation: { doc: "QĐ-TT/2026", path: "Điều 7 / Khoản 1" },
    });
    expect(body[1]).toMatchObject({ code: "outline", required_evidence: [], linked_to: "outline", citation: {} });
    expect(await screen.findByText("Đã lưu mẫu mốc")).toBeInTheDocument();
  });

  it("lưu xong tải lại dữ liệu đợt", async () => {
    const user = await setup();
    await user.click(screen.getByRole("button", { name: "Lưu mẫu mốc" }));
    await waitFor(() => expect(api.mock.calls.filter((c) => c[1] === "/admin/cohort" && c[0] === "GET")).toHaveLength(2));
  });
});

describe("AdminHome — phân công giảng viên", () => {
  it("mỗi sinh viên một ô chọn, đang chọn đúng GV hiện tại; chỉ liệt kê giảng viên", async () => {
    await setup();
    const select = screen.getByLabelText("GV phụ trách Nguyễn Văn An");
    expect(select).toHaveValue("1");
    expect([...select.options].map((o) => o.textContent)).toEqual(["TS. Trần", "TS. Lê"]);
    expect(screen.getByLabelText("GV phụ trách Lê Thị Bình")).toHaveValue("2");
  });

  it("đổi GV: POST /admin/assign với id dạng số và báo đã phân công", async () => {
    const user = await setup();
    await user.selectOptions(screen.getByLabelText("GV phụ trách Nguyễn Văn An"), "2");
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/admin/assign", { student_id: 10, lecturer_id: 2 }));
    expect(await screen.findByText("Đã phân công")).toBeInTheDocument();
  });
});

describe("AdminHome — thêm tài khoản", () => {
  const fill = async (user, { code = "", role } = {}) => {
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv99");
    await user.type(screen.getByLabelText("Mật khẩu"), "matkhau1");
    await user.type(screen.getByLabelText("Họ tên"), "Phạm Văn Cường");
    if (role) await user.selectOptions(screen.getByLabelText("Vai trò"), role);
    if (code) await user.type(screen.getByLabelText("Mã SV"), code);
  };

  it("tạo sinh viên: gửi đủ trường, tải lại và xóa form", async () => {
    const user = await setup();
    await fill(user, { code: "SV099" });
    await user.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    await waitFor(() => expect(writes().some((c) => c[1] === "/admin/users")).toBe(true));
    const [, , body] = writes().find((c) => c[1] === "/admin/users");
    expect(body).toMatchObject({ username: "sv99", password: "matkhau1", full_name: "Phạm Văn Cường", role: "student", student_code: "SV099" });
    expect(await screen.findByText("Đã tạo tài khoản")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Tên đăng nhập")).toHaveValue(""));
  });

  it("không nhập mã SV (vd. giảng viên) thì không gửi student_code", async () => {
    const user = await setup();
    await fill(user, { role: "lecturer" });
    await user.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    await waitFor(() => expect(writes().some((c) => c[1] === "/admin/users")).toBe(true));
    const [, , body] = writes().find((c) => c[1] === "/admin/users");
    expect(body.role).toBe("lecturer");
    expect(body).not.toHaveProperty("student_code");
  });

  it("thiếu trường bắt buộc thì không gửi", async () => {
    const user = await setup();
    await user.type(screen.getByLabelText("Tên đăng nhập"), "sv99");
    await user.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
    expect(writes().some((c) => c[1] === "/admin/users")).toBe(false);
  });

  it("form có đủ hai vai trò để chọn", async () => {
    await setup();
    const role = screen.getByLabelText("Vai trò");
    expect(within(role).getAllByRole("option").map((o) => o.textContent)).toEqual(["Sinh viên", "Giảng viên"]);
  });
});
