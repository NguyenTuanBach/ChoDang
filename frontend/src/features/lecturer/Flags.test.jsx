import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import Flags from "./Flags";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

const flag = (over = {}) => ({
  id: 1, internship_id: 9, severity: "warning", status: "open", reason: "Mốc giữa kỳ đã quá hạn 3 ngày",
  created_at: "2027-02-05T03:00:00", student: { full_name: "Nguyễn Văn An" }, ...over,
});

const setup = (flags) => {
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/risk-flags") return flags;
    return {};
  });
  render(<MemoryRouter><ToastProvider><Flags /></ToastProvider></MemoryRouter>);
  return userEvent.setup();
};

const getCalls = () => api.mock.calls.filter((c) => c[0] === "GET" && c[1] === "/risk-flags");

beforeEach(() => {
  api.mockReset();
});

describe("Flags — danh sách cảnh báo", () => {
  it("không có cảnh báo đang mở → hiện thông báo trống", async () => {
    setup([]);
    expect(await screen.findByText("Không có cảnh báo đang mở.")).toBeInTheDocument();
  });

  it("hiện mức độ, tên sinh viên (link tới hồ sơ), lý do và trạng thái", async () => {
    setup([flag()]);
    expect(await screen.findByText("Mốc giữa kỳ đã quá hạn 3 ngày")).toBeInTheDocument();
    expect(screen.getByText("Cảnh báo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nguyễn Văn An" })).toHaveAttribute("href", "/internship/9");
  });

  it("nói rõ tác tử chỉ cảnh báo, không đổi trạng thái hồ sơ", async () => {
    setup([flag()]);
    await screen.findByText("Mốc giữa kỳ đã quá hạn 3 ngày");
    expect(screen.getByText(/tác tử không thay đổi trạng thái hồ sơ/)).toBeInTheDocument();
  });

  it("lỗi tải → hiện lỗi thay vì danh sách", async () => {
    api.mockRejectedValue(new Error("Không có quyền"));
    render(<MemoryRouter><ToastProvider><Flags /></ToastProvider></MemoryRouter>);
    expect(await screen.findByText("Không có quyền")).toBeInTheDocument();
  });
});

describe("Flags — xử lý cảnh báo", () => {
  it("cảnh báo đã ghi nhận không còn nút Ghi nhận nữa", async () => {
    setup([flag({ id: 1, status: "open" }), flag({ id: 2, status: "acknowledged", reason: "Lý do khác" })]);
    await screen.findByText("Lý do khác");
    expect(screen.getAllByRole("button", { name: "Ghi nhận" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Bác bỏ" })).toHaveLength(2);
  });

  it.each([
    ["Ghi nhận", "acknowledge"],
    ["Đã xử lý", "resolve"],
    ["Bác bỏ", "dismiss"],
  ])("nút %s gửi action %s kèm ghi chú rồi tải lại danh sách", async (label, action) => {
    const user = setup([flag({ id: 5 })]);
    await screen.findByText("Mốc giữa kỳ đã quá hạn 3 ngày");
    await user.type(screen.getByLabelText("Ghi chú"), "Đã nhắc sinh viên");
    await user.click(screen.getByRole("button", { name: label }));
    await waitFor(() => expect(getCalls()).toHaveLength(2));
    expect(api).toHaveBeenCalledWith("PATCH", "/risk-flags/5", { action, note: "Đã nhắc sinh viên" });
  });

  it("bác bỏ thiếu ghi chú (máy chủ từ chối): hiện lỗi, không tải lại, giữ ô ghi chú", async () => {
    const user = setup([flag()]);
    await screen.findByText("Mốc giữa kỳ đã quá hạn 3 ngày");
    api.mockImplementation(async (method) => { if (method === "PATCH") throw new Error("Cần ghi chú khi bác bỏ"); return []; });
    await user.type(screen.getByLabelText("Ghi chú"), "x");
    await user.click(screen.getByRole("button", { name: "Bác bỏ" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Cần ghi chú khi bác bỏ");
    expect(getCalls()).toHaveLength(1);
    expect(screen.getByLabelText("Ghi chú")).toHaveValue("x");
  });

  it("ghi chú của từng cảnh báo độc lập với nhau", async () => {
    const user = setup([flag({ id: 1 }), flag({ id: 2, reason: "Cảnh báo thứ hai" })]);
    await screen.findByText("Cảnh báo thứ hai");
    const [first, second] = screen.getAllByLabelText("Ghi chú");
    await user.type(first, "chỉ cho cờ 1");
    expect(second).toHaveValue("");
    await user.click(within(first.closest(".list-item")).getByRole("button", { name: "Đã xử lý" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("PATCH", "/risk-flags/1", { action: "resolve", note: "chỉ cho cờ 1" }));
  });
});
