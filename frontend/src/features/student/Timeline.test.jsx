import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import Timeline, { currentMilestone } from "./Timeline";

vi.mock("../../lib/api", () => ({ api: vi.fn(), formData: (o) => o })); // formData trả nguyên object để kiểm tra nội dung gửi đi
vi.mock("../shared/EvidenceLink", () => ({ EvidenceLink: ({ id, children }) => <a data-testid={`ev-${id}`}>{children}</a> }));
let role = "student";
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    me: { role },
    config: { evidence_types: { final_report: "Báo cáo cuối kỳ", receipt: "Giấy tiếp nhận", other: "Khác" } },
  }),
}));

const ms = (over = {}) => ({
  id: 1, name: "Nộp giấy tiếp nhận", status: "pending", due_date: "2027-02-01", days_left: 5,
  required_evidence: [], evidence: [], comment: null, citation: null, linked_to: null, ...over,
});
const internship = (milestones) => ({ id: 3, milestones });

const setup = (milestones) => {
  const reload = vi.fn();
  const view = render(<ToastProvider><Timeline internship={internship(milestones)} reload={reload} /></ToastProvider>);
  return { reload, user: userEvent.setup(), ...view };
};
const pdf = () => new File(["%PDF-1.4"], "bao-cao.pdf", { type: "application/pdf" });

beforeEach(() => {
  api.mockReset();
  role = "student";
});

describe("Timeline — hiển thị các mốc", () => {
  it("currentMilestone là mốc đầu tiên chưa được chấp nhận", () => {
    const list = [ms({ id: 1, status: "accepted" }), ms({ id: 2, status: "submitted" }), ms({ id: 3, status: "pending" })];
    expect(currentMilestone({ milestones: list }).id).toBe(2);
    expect(currentMilestone({ milestones: [ms({ status: "accepted" })] })).toBeUndefined();
  });

  it("hiện tên, hạn và số ngày còn lại / đã quá", () => {
    setup([ms({ id: 1, name: "Mốc A", days_left: 5 }), ms({ id: 2, name: "Mốc B", days_left: -3, status: "overdue" })]);
    expect(screen.getByText(`Hạn ${fmtDate("2027-02-01")} · còn 5 ngày`)).toBeInTheDocument();
    expect(screen.getByText(`Hạn ${fmtDate("2027-02-01")} · quá 3 ngày`)).toBeInTheDocument();
  });

  it("mốc đã được chấp nhận không hiện số ngày", () => {
    setup([ms({ status: "accepted", days_left: 5 })]);
    expect(screen.getByText(`Hạn ${fmtDate("2027-02-01")}`)).toBeInTheDocument();
    expect(screen.queryByText(/còn 5 ngày/)).not.toBeInTheDocument();
  });

  it("chỉ mốc hiện tại có aria-current và nhãn 'Chặng tiếp theo'", () => {
    const { container } = setup([ms({ id: 1, status: "accepted", name: "Xong rồi" }), ms({ id: 2, name: "Đang làm" }), ms({ id: 3, name: "Sau đó" })]);
    const current = container.querySelectorAll("[aria-current='step']");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Đang làm");
    expect(screen.getAllByText("Chặng tiếp theo")).toHaveLength(1);
  });

  it("hiện minh chứng yêu cầu theo tên loại, file đã tải, nhận xét GV và căn cứ", () => {
    setup([ms({
      required_evidence: ["final_report", "unknown_type"],
      evidence: [{ id: 11, filename: "bao-cao.pdf" }],
      comment: "Thiếu chữ ký",
      citation: { doc: "QĐ-TT/2026", path: "Điều 7" },
    })]);
    expect(screen.getByText("Minh chứng yêu cầu: Báo cáo cuối kỳ, unknown_type")).toBeInTheDocument();
    expect(screen.getByTestId("ev-11")).toHaveTextContent("bao-cao.pdf");
    expect(screen.getByText("Nhận xét GV: Thiếu chữ ký")).toBeInTheDocument();
    expect(screen.getByText("Căn cứ: QĐ-TT/2026 · Điều 7")).toBeInTheDocument();
  });

  it("mốc gắn với đề cương hiện ghi chú 'cập nhật theo đề cương'", () => {
    setup([ms({ linked_to: "outline" })]);
    expect(screen.getByText(/cập nhật theo đề cương/)).toBeInTheDocument();
  });
});

describe("Timeline — ai được thao tác", () => {
  it.each(["pending", "overdue", "rejected"])("sinh viên thao tác được khi mốc %s", (status) => {
    setup([ms({ status })]);
    expect(screen.getByRole("button", { name: "Nộp mốc" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xin gia hạn" })).toBeInTheDocument();
  });

  it.each(["submitted", "accepted"])("mốc %s không còn nút thao tác", (status) => {
    setup([ms({ status })]);
    expect(screen.queryByRole("button", { name: "Nộp mốc" })).not.toBeInTheDocument();
  });

  it("mốc theo đề cương không nộp tay được", () => {
    setup([ms({ linked_to: "outline" })]);
    expect(screen.queryByRole("button", { name: "Nộp mốc" })).not.toBeInTheDocument();
  });

  it("giảng viên chỉ xem, không có nút nào", () => {
    role = "lecturer";
    setup([ms()]);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("Timeline — nộp minh chứng và mốc", () => {
  it("loại minh chứng mặc định là loại mốc yêu cầu", () => {
    setup([ms({ required_evidence: ["final_report"] })]);
    expect(screen.getByLabelText("Loại minh chứng")).toHaveValue("final_report");
  });

  it("tải minh chứng: gửi file kèm loại đã chọn rồi tải lại", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup([ms({ id: 4 })]);
    await user.selectOptions(screen.getByLabelText("Loại minh chứng"), "receipt");
    const file = pdf();
    fireEvent.change(document.querySelector("input[type=file]"), { target: { files: [file] } });
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(api).toHaveBeenCalledWith("POST", "/milestones/4/evidence", { file, evidence_type: "receipt" }, true);
  });

  it("nộp mốc: POST rồi tải lại", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup([ms({ id: 4 })]);
    await user.click(screen.getByRole("button", { name: "Nộp mốc" }));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(api).toHaveBeenCalledWith("POST", "/milestones/4/submit");
  });
});

describe("Timeline — API lỗi", () => {
  it("tải minh chứng lỗi: hiện lỗi, không tải lại", async () => {
    api.mockRejectedValue(new Error("File PDF bị hỏng"));
    const { reload } = setup([ms()]);
    fireEvent.change(document.querySelector("input[type=file]"), { target: { files: [pdf()] } });
    expect(await screen.findByRole("status")).toHaveTextContent("File PDF bị hỏng");
    expect(reload).not.toHaveBeenCalled();
  });

  it("nộp mốc lỗi (vd. thiếu minh chứng): hiện lỗi, không tải lại", async () => {
    api.mockRejectedValue(new Error("Chưa đủ minh chứng"));
    const { user, reload } = setup([ms()]);
    await user.click(screen.getByRole("button", { name: "Nộp mốc" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Chưa đủ minh chứng");
    expect(reload).not.toHaveBeenCalled();
  });

  it("gia hạn bị từ chối (quá hạn xin): hiện lỗi kèm căn cứ, giữ form để sửa", async () => {
    api.mockRejectedValue(new Error("Đã quá thời hạn xin gia hạn (QĐ-TT/2026 · Điều 10 / Khoản 2)"));
    const { user, reload } = setup([ms()]);
    await user.click(screen.getByRole("button", { name: "Xin gia hạn" }));
    fireEvent.change(screen.getByLabelText("Hạn mới đề xuất"), { target: { value: "2027-02-10" } });
    await user.click(screen.getByRole("button", { name: "Gửi yêu cầu" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Điều 10 / Khoản 2");
    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: /Xin gia hạn:/ })).toBeInTheDocument();
  });

  it("tải minh chứng cho gia hạn lỗi thì không gửi yêu cầu gia hạn", async () => {
    api.mockRejectedValue(new Error("File quá 10 MB"));
    const { user } = setup([ms({ id: 4 })]);
    await user.click(screen.getByRole("button", { name: "Xin gia hạn" }));
    fireEvent.change(screen.getByLabelText(/Minh chứng cho lý do/), { target: { files: [pdf()] } });
    await user.click(screen.getByRole("button", { name: "Gửi yêu cầu" }));
    expect(await screen.findByRole("status")).toHaveTextContent("File quá 10 MB");
    expect(api).toHaveBeenCalledTimes(1);
    expect(api).not.toHaveBeenCalledWith("POST", "/milestones/4/extensions", expect.anything());
  });
});

describe("Timeline — xin gia hạn", () => {
  it("bấm Xin gia hạn mở form kèm căn cứ 14 ngày; bấm lần nữa thì đóng", async () => {
    const { user } = setup([ms({ name: "Mốc A" })]);
    await user.click(screen.getByRole("button", { name: "Xin gia hạn" }));
    expect(screen.getByRole("heading", { name: "Xin gia hạn: Mốc A" })).toBeInTheDocument();
    expect(screen.getByText(/không quá 14 ngày/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Xin gia hạn" }));
    expect(screen.queryByRole("heading", { name: /Xin gia hạn:/ })).not.toBeInTheDocument();
  });

  it("gửi yêu cầu không kèm file: chỉ POST extensions với hạn mới và lý do", async () => {
    api.mockResolvedValue({});
    const { user, reload } = setup([ms({ id: 4 })]);
    await user.click(screen.getByRole("button", { name: "Xin gia hạn" }));
    fireEvent.change(screen.getByLabelText("Hạn mới đề xuất"), { target: { value: "2027-02-10" } });
    await user.type(screen.getByLabelText("Lý do"), "Sinh viên bị ốm");
    await user.click(screen.getByRole("button", { name: "Gửi yêu cầu" }));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(api).toHaveBeenCalledTimes(1);
    expect(api).toHaveBeenCalledWith("POST", "/milestones/4/extensions", { requested_due_date: "2027-02-10", reason: "Sinh viên bị ốm" });
    expect(screen.queryByRole("heading", { name: /Xin gia hạn:/ })).not.toBeInTheDocument();
  });

  it("có file minh chứng: tải file (loại 'other') trước, rồi gửi yêu cầu kèm evidence_id", async () => {
    api.mockImplementation(async (_m, path) => (path.endsWith("/evidence") ? { id: 99 } : {}));
    const { user, reload } = setup([ms({ id: 4 })]);
    await user.click(screen.getByRole("button", { name: "Xin gia hạn" }));
    fireEvent.change(screen.getByLabelText("Hạn mới đề xuất"), { target: { value: "2027-02-10" } });
    await user.type(screen.getByLabelText("Lý do"), "Ốm");
    const file = pdf();
    fireEvent.change(screen.getByLabelText(/Minh chứng cho lý do/), { target: { files: [file] } });
    await user.click(screen.getByRole("button", { name: "Gửi yêu cầu" }));
    await waitFor(() => expect(reload).toHaveBeenCalled());
    expect(api.mock.calls[0]).toEqual(["POST", "/milestones/4/evidence", { file, evidence_type: "other" }, true]);
    expect(api.mock.calls[1]).toEqual(["POST", "/milestones/4/extensions", { requested_due_date: "2027-02-10", reason: "Ốm", evidence_id: 99 }]);
  });
});
