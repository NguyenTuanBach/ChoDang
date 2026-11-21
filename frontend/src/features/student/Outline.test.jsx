import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import Outline from "./Outline";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

let mockRole = "student";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role: mockRole } }) }));

const internship = (outline) => ({ id: 5, outline });
const setup = (outline, role = "student") => {
  mockRole = role;
  const reload = vi.fn();
  render(<ToastProvider><Outline internship={internship(outline)} reload={reload} /></ToastProvider>);
  return { reload, user: userEvent.setup() };
};

beforeEach(() => {
  api.mockReset();
  mockRole = "student";
});

describe("Outline — sinh viên nộp", () => {
  it("chưa có đề cương: ô nhập trống, không có badge trạng thái", () => {
    setup(null);
    expect(screen.getByRole("textbox")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Nộp đề cương" })).toBeInTheDocument();
    expect(document.querySelector(".badge")).toBeNull();
  });

  it("nộp đề cương: POST nội dung đã gõ rồi tải lại", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup(null);
    await user.type(screen.getByRole("textbox"), "Kế hoạch 8 tuần");
    await user.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(api).toHaveBeenCalledWith("POST", "/internships/5/outline", { content: "Kế hoạch 8 tuần" });
    expect(await screen.findByRole("status")).toHaveTextContent("Đã nộp đề cương");
  });

  it("server từ chối (vd. dưới 50 ký tự) → hiện lỗi, không tải lại", async () => {
    api.mockRejectedValue(new Error("Đề cương tối thiểu 50 ký tự"));
    const { user, reload } = setup(null);
    await user.type(screen.getByRole("textbox"), "ngắn");
    await user.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Đề cương tối thiểu 50 ký tự");
    expect(reload).not.toHaveBeenCalled();
  });

  it.each(["revision_requested", "rejected"])("đề cương '%s': sửa và nộp lại, điền sẵn nội dung cũ kèm nhận xét GV", async (status) => {
    api.mockResolvedValue({});
    const { user } = setup({ status, content: "Bản cũ", reason: "Thiếu kế hoạch kiểm thử" });
    expect(screen.getByRole("textbox")).toHaveValue("Bản cũ");
    const note = screen.getByText("Nhận xét GV: Thiếu kế hoạch kiểm thử");
    expect(note).toHaveClass("errors");
    await user.type(screen.getByRole("textbox"), " + kiểm thử");
    await user.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/internships/5/outline", { content: "Bản cũ + kiểm thử" }));
  });
});

describe("Outline — chỉ xem", () => {
  it.each(["submitted", "approved"])("đề cương '%s': chỉ đọc, không có ô nhập hay nút nộp", (status) => {
    setup({ status, content: "Nội dung đã nộp", reason: "" });
    expect(screen.getByText("Nội dung đã nộp")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nộp đề cương" })).not.toBeInTheDocument();
  });

  it("đề cương đã duyệt: nhận xét hiện dạng thường (không phải lỗi)", () => {
    setup({ status: "approved", content: "x", reason: "Đạt" });
    expect(screen.getByText("Nhận xét GV: Đạt")).toHaveClass("muted");
    expect(screen.getByText("Nhận xét GV: Đạt")).not.toHaveClass("errors");
  });

  it("không có nhận xét thì không hiện dòng nhận xét", () => {
    setup({ status: "submitted", content: "x", reason: "" });
    expect(screen.queryByText(/Nhận xét GV/)).not.toBeInTheDocument();
  });

  it.each(["lecturer", "admin"])("vai trò %s không nộp được đề cương dù chưa có", (role) => {
    setup(null, role);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nộp đề cương" })).not.toBeInTheDocument();
  });

  it("vai trò giảng viên với đề cương bị yêu cầu sửa vẫn không có ô nhập", () => {
    setup({ status: "revision_requested", content: "x", reason: "sửa" }, "lecturer");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
