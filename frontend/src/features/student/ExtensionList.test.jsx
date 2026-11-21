import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import ExtensionList from "./ExtensionList";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
let role = "student";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role } }) }));

const ext = (over = {}) => ({
  id: 1, status: "open", milestone: { name: "Báo cáo giữa kỳ" },
  previous_due_date: "2027-02-01", requested_due_date: "2027-02-10", reason: "Sinh viên bị ốm", decision_reason: null, ...over,
});

const setup = (extensions) => {
  const reload = vi.fn();
  render(<ToastProvider><ExtensionList extensions={extensions} reload={reload} /></ToastProvider>);
  return { reload, user: userEvent.setup() };
};

beforeEach(() => {
  api.mockReset();
  role = "student";
});

describe("ExtensionList", () => {
  it("hiện tên mốc, hạn cũ → hạn mới và lý do", () => {
    setup([ext()]);
    expect(screen.getByText("Báo cáo giữa kỳ")).toBeInTheDocument();
    expect(screen.getByText(`${fmtDate("2027-02-01")} → ${fmtDate("2027-02-10")} · Sinh viên bị ốm`)).toBeInTheDocument();
  });

  it("hiện nhận xét của giảng viên khi đã có quyết định", () => {
    setup([ext({ status: "rejected", decision_reason: "Thiếu giấy khám bệnh" })]);
    expect(screen.getByText("GV: Thiếu giấy khám bệnh")).toBeInTheDocument();
  });

  it("không có yêu cầu nào thì chỉ còn tiêu đề", () => {
    setup([]);
    expect(screen.getByRole("heading", { name: "Yêu cầu gia hạn" })).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("chỉ yêu cầu đang chờ mới có nút Hủy", () => {
    setup([ext({ id: 1, status: "open" }), ext({ id: 2, status: "approved" }), ext({ id: 3, status: "rejected" })]);
    expect(screen.getAllByRole("button", { name: "Hủy" })).toHaveLength(1);
  });

  it("giảng viên không được hủy yêu cầu của sinh viên", () => {
    role = "lecturer";
    setup([ext()]);
    expect(screen.queryByRole("button", { name: "Hủy" })).not.toBeInTheDocument();
  });

  it("hủy lỗi (vd. yêu cầu đã được duyệt): hiện lỗi, không tải lại", async () => {
    api.mockRejectedValue(new Error("Yêu cầu đã được xử lý"));
    const { user, reload } = setup([ext()]);
    await user.click(screen.getByRole("button", { name: "Hủy" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Yêu cầu đã được xử lý");
    expect(reload).not.toHaveBeenCalled();
  });

  it("hủy: POST đúng endpoint rồi tải lại", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup([ext({ id: 7 })]);
    await user.click(screen.getByRole("button", { name: "Hủy" }));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(api).toHaveBeenCalledWith("POST", "/extensions/7/cancel");
  });
});
