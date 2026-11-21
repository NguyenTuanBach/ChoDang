import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import ExceptionPanel, { ExceptionAi, exceptionDetail } from "./ExceptionPanel";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
let role = "student";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role } }) }));

const internship = { id: 3, milestones: [
  { id: 11, name: "Báo cáo giữa kỳ", status: "overdue", due_date: "2027-02-01" },
  { id: 12, name: "Giấy tiếp nhận", status: "accepted", due_date: "2027-01-10" },
] };
const late = (over = {}) => ({
  id: 1, kind: "late_extension", status: "open", reason: "Doanh nghiệp đổi lịch", decision_reason: null,
  milestone: { name: "Báo cáo giữa kỳ" }, payload: { previous_due_date: "2027-02-01", requested_due_date: "2027-02-10" }, ...over,
});

const setup = (exceptions = []) => {
  const reload = vi.fn();
  render(<ToastProvider><ExceptionPanel internship={internship} exceptions={exceptions} reload={reload} /></ToastProvider>);
  return { reload, user: userEvent.setup() };
};

beforeEach(() => {
  api.mockReset();
  role = "student";
});

describe("ExceptionPanel", () => {
  it("hiện loại, trạng thái, chi tiết và nhận xét của giảng viên", () => {
    setup([late({ status: "rejected", decision_reason: "Thiếu xác nhận" })]);
    expect(screen.getByText("Gia hạn quá hạn", { selector: "b" })).toBeInTheDocument();
    expect(screen.getByText(/Báo cáo giữa kỳ: /)).toBeInTheDocument();
    expect(screen.getByText("GV: Thiếu xác nhận")).toBeInTheDocument();
  });

  it("chỉ yêu cầu đang chờ mới có nút Hủy và hủy gọi đúng API", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup([late({ id: 1 }), late({ id: 2, status: "approved" })]);
    expect(screen.getAllByRole("button", { name: "Hủy" })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Hủy" }));
    await waitFor(() => expect(reload).toHaveBeenCalled());
    expect(api).toHaveBeenCalledWith("POST", "/exceptions/1/cancel");
  });

  it("gửi ngoại lệ gia hạn: chỉ liệt kê mốc chưa chấp nhận, nút gửi chờ đủ lý do", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup();
    await user.click(screen.getByRole("button", { name: "Gia hạn quá hạn" }));
    expect(screen.queryByRole("option", { name: /Giấy tiếp nhận/ })).not.toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Gửi yêu cầu" });
    expect(send).toBeDisabled();
    await user.type(screen.getByLabelText("Hạn mới đề nghị"), "2027-02-20");
    await user.type(screen.getByLabelText(/Lý do/), "Doanh nghiệp đổi lịch dự án");
    await user.click(send);
    await waitFor(() => expect(reload).toHaveBeenCalled());
    expect(api).toHaveBeenCalledWith("POST", "/internships/3/exceptions", {
      kind: "late_extension", reason: "Doanh nghiệp đổi lịch dự án", milestone_id: 11,
      payload: { requested_due_date: "2027-02-20" },
    });
  });

  it("gửi ngoại lệ công nhận tín chỉ kèm số tín chỉ", async () => {
    api.mockResolvedValue({});
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Công nhận tín chỉ" }));
    await user.type(screen.getByLabelText(/Số tín chỉ/), "4");
    await user.type(screen.getByLabelText(/Lý do/), "Đề nghị quy đổi tín chỉ");
    await user.click(screen.getByRole("button", { name: "Gửi yêu cầu" }));
    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(api.mock.calls[0][2]).toMatchObject({ kind: "credit_recognition", payload: { credits: 4, basis: "" } });
  });

  it("lỗi từ máy chủ: giữ nguyên form và không tải lại", async () => {
    api.mockRejectedValue(new Error("Hạn mới phải sau hạn hiện tại"));
    const { user, reload } = setup();
    await user.click(screen.getByRole("button", { name: "Gia hạn quá hạn" }));
    await user.type(screen.getByLabelText(/Lý do/), "Doanh nghiệp đổi lịch dự án");
    await user.click(screen.getByRole("button", { name: "Gửi yêu cầu" }));
    expect(await screen.findByText("Hạn mới phải sau hạn hiện tại")).toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Gửi yêu cầu" })).toBeInTheDocument();
  });

  it("vai trò khác sinh viên không có nút gửi/hủy", () => {
    role = "lecturer";
    setup([late()]);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("helpers", () => {
  it("exceptionDetail mô tả theo loại", () => {
    expect(exceptionDetail({ kind: "credit_recognition", payload: { credits: 4, basis: "CS101" } })).toBe("Đề nghị công nhận 4 tín chỉ · CS101");
  });
  it("ExceptionAi không hiện gì khi AI lỗi", () => {
    const { container } = render(<ExceptionAi summary={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
