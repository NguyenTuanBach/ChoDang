import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import Policies from "./Policies";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
let canManage = false;
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { can_manage_policies: canManage } }) }));

const doc = (over = {}) => ({
  id: 1, code: "QĐ-TT/2026", title: "Quy định thực tập 2026", issuer: "Phòng Đào tạo",
  effective_from: "2026-09-01", effective_to: null, status: "active", chunk_count: 12, ...over,
});

const setup = (docs = [doc()]) => {
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/policies") return docs;
    if (method === "GET" && path === "/policies/1") return { code: "QĐ-TT/2026", title: "Quy định thực tập 2026", chunks: [{ path: "Điều 3 / Khoản 1", text: "Tối thiểu 8 tuần." }, { path: "Điều 8", text: "Nhật ký hằng tuần." }] };
    return {};
  });
  render(<ToastProvider><Policies /></ToastProvider>);
  return userEvent.setup();
};

const submitForm = () => {
  const form = screen.getByRole("button", { name: "Tải lên & lập chỉ mục" }).closest("form");
  form.noValidate = true;
  fireEvent.submit(form);
};

beforeEach(() => {
  api.mockReset();
  canManage = false;
});

describe("Policies — danh sách văn bản", () => {
  it("hiện số hiệu, tên, cơ quan ban hành, hiệu lực và số đoạn", async () => {
    setup();
    expect(await screen.findByRole("button", { name: "QĐ-TT/2026" })).toBeInTheDocument();
    expect(screen.getByText("Quy định thực tập 2026")).toBeInTheDocument();
    expect(screen.getByText("Phòng Đào tạo")).toBeInTheDocument();
    expect(screen.getByText(fmtDate("2026-09-01"))).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("văn bản đã bị thay thế có khoảng hiệu lực đóng", async () => {
    setup([doc({ effective_to: "2026-08-31", status: "superseded" })]);
    expect(await screen.findByText(`${fmtDate("2026-09-01")} – ${fmtDate("2026-08-31")}`)).toBeInTheDocument();
  });

  it("lỗi tải → hiện lỗi", async () => {
    api.mockRejectedValue(new Error("Phiên đăng nhập hết hạn"));
    render(<ToastProvider><Policies /></ToastProvider>);
    expect(await screen.findByText("Phiên đăng nhập hết hạn")).toBeInTheDocument();
  });

  it("bấm số hiệu: tải nội dung và hiện từng điều khoản có thể xổ ra", async () => {
    const user = setup();
    await user.click(await screen.findByRole("button", { name: "QĐ-TT/2026" }));
    expect(await screen.findByRole("heading", { name: "QĐ-TT/2026 — Quy định thực tập 2026" })).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("GET", "/policies/1");
    await user.click(screen.getByText("Điều 3 / Khoản 1"));
    expect(screen.getByText("Tối thiểu 8 tuần.")).toBeInTheDocument();
    expect(screen.getByText("Điều 8")).toBeInTheDocument();
  });
});

describe("Policies — tải văn bản mới (HITL: chỉ người có quyền)", () => {
  it("người không có quyền không thấy form tải lên", async () => {
    setup();
    await screen.findByRole("button", { name: "QĐ-TT/2026" });
    expect(screen.queryByText("Tải văn bản mới")).not.toBeInTheDocument();
  });

  it("người có quyền thấy form; gửi FormData đầy đủ, bỏ trường thay thế khi để trống", async () => {
    canManage = true;
    const user = setup();
    await screen.findByText("Tải văn bản mới");
    await user.type(screen.getByLabelText("Số hiệu"), "QĐ-TT/2027");
    await user.type(screen.getByLabelText("Tên văn bản"), "Quy định thực tập 2027");
    fireEvent.change(screen.getByLabelText("Hiệu lực từ"), { target: { value: "2027-01-01" } });
    await user.type(screen.getByLabelText("Cơ quan ban hành"), "Phòng Đào tạo");
    submitForm(); // jsdom không đưa file vào FormData của form nên bỏ qua kiểm tra ràng buộc; trình duyệt thật vẫn bắt buộc chọn file

    await waitFor(() => expect(api.mock.calls.some((c) => c[0] === "POST")).toBe(true));
    const [method, path, body, isForm] = api.mock.calls.find((c) => c[0] === "POST");
    expect([method, path, isForm]).toEqual(["POST", "/policies", true]);
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("code")).toBe("QĐ-TT/2027");
    expect(body.get("title")).toBe("Quy định thực tập 2027");
    expect(body.get("effective_from")).toBe("2027-01-01");
    expect(body.get("issuer")).toBe("Phòng Đào tạo");
    expect(body.has("supersedes_code")).toBe(false);
    expect(await screen.findByText("Đã tải và lập chỉ mục văn bản")).toBeInTheDocument();
  });

  it("có nhập số hiệu văn bản bị thay thế thì gửi kèm", async () => {
    canManage = true;
    const user = setup();
    await screen.findByText("Tải văn bản mới");
    await user.type(screen.getByLabelText("Số hiệu"), "QĐ-TT/2027");
    await user.type(screen.getByLabelText("Tên văn bản"), "Quy định 2027");
    fireEvent.change(screen.getByLabelText("Hiệu lực từ"), { target: { value: "2027-01-01" } });
    await user.type(screen.getByLabelText(/Thay thế văn bản/), "QĐ-TT/2026");
    submitForm();
    await waitFor(() => expect(api.mock.calls.some((c) => c[0] === "POST")).toBe(true));
    expect(api.mock.calls.find((c) => c[0] === "POST")[2].get("supersedes_code")).toBe("QĐ-TT/2026");
  });

  it("thiếu file hoặc trường bắt buộc thì không gửi", async () => {
    canManage = true;
    const user = setup();
    await screen.findByText("Tải văn bản mới");
    await user.type(screen.getByLabelText("Số hiệu"), "QĐ-TT/2027");
    await user.click(screen.getByRole("button", { name: "Tải lên & lập chỉ mục" }));
    expect(api.mock.calls.some((c) => c[0] === "POST")).toBe(false);
  });
});
