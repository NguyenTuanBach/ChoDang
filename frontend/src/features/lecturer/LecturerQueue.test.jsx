import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import LecturerQueue from "./LecturerQueue";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

const STUDENT = { full_name: "Nguyễn Văn An" };
const INTERNSHIP = {
  id: 1, version: 2, status: "submitted", student: STUDENT, ai_fields: ["company_tax_code"],
  company_name: "Công ty Sao Mai", company_tax_code: "0101234567", mode: "part_time", start_date: "2027-01-05",
};
const OUTLINE = {
  id: 7, version: 3, internship: { student: { full_name: "Trần Thị Bình" } }, content: "Xây dựng API backend.",
  ai_summary: { label: "Gợi ý của AI — chỉ để tham khảo", summary: "Đề cương về backend.", uncovered_outcomes: [{ code: "CLO2", text: "Triển khai" }] },
};
const EXTENSION = {
  id: 9, student: { full_name: "Lê Văn Cường" }, milestone: { name: "Báo cáo giữa kỳ" }, reason: "Ốm 2 tuần",
  previous_due_date: "2027-02-01", requested_due_date: "2027-02-15", evidence_id: 4,
  ai_summary: { label: "Gợi ý của AI", summary: "Xin dời 14 ngày.", related_clauses: [{ label: "Điều 10", text: "Gia hạn khi có lý do chính đáng" }] },
};

const queue = (over = {}) => ({ internships: [], outlines: [], extensions: [], ...over });

const setup = (data) => {
  api.mockImplementation(async (method, path) => (path === "/approvals/queue" ? data : {}));
  render(<ToastProvider><LecturerQueue /></ToastProvider>);
  return userEvent.setup();
};

beforeEach(() => {
  api.mockReset();
});

describe("LecturerQueue", () => {
  it("hàng chờ trống → thông báo không có mục nào", async () => {
    setup(queue());
    expect(await screen.findByText("Không có mục nào chờ duyệt.")).toBeInTheDocument();
  });

  it("đếm tổng số mục chờ xử lý (hồ sơ + đề cương + gia hạn)", async () => {
    setup(queue({ internships: [INTERNSHIP], outlines: [OUTLINE], extensions: [EXTENSION] }));
    expect(await screen.findByText("3 mục đang chờ bạn xử lý")).toBeInTheDocument();
  });

  it("lỗi tải hàng chờ → hiện thông báo lỗi", async () => {
    api.mockRejectedValue(new Error("Không có quyền"));
    render(<ToastProvider><LecturerQueue /></ToastProvider>);
    expect(await screen.findByText("Không có quyền")).toBeInTheDocument();
  });

  it("thẻ hồ sơ: hiện thông tin sinh viên, đánh dấu trường do AI điền, hình thức bằng tiếng Việt", async () => {
    setup(queue({ internships: [INTERNSHIP] }));
    expect(await screen.findByText("Nguyễn Văn An")).toBeInTheDocument();
    expect(screen.getByText("0101234567")).toBeInTheDocument();
    expect(screen.getByText("Bán thời gian")).toBeInTheDocument();
    const taxRow = screen.getByText("0101234567").closest("div");
    expect(within(taxRow).getByText("AI điền")).toBeInTheDocument();
    expect(screen.getAllByText("AI điền")).toHaveLength(1);
  });

  it("duyệt hồ sơ: POST kèm version rồi tải lại hàng chờ", async () => {
    const user = setup(queue({ internships: [INTERNSHIP] }));
    await user.click(await screen.findByRole("button", { name: "Duyệt" }));
    await waitFor(() => expect(api.mock.calls.filter((c) => c[1] === "/approvals/queue")).toHaveLength(2));
    expect(api).toHaveBeenCalledWith("POST", "/internships/1/decision", { decision: "approved", reason: "", version: 2 });
  });

  it("thẻ đề cương: nội dung, tóm tắt AI có nhãn, chuẩn đầu ra chưa nhắc tới", async () => {
    setup(queue({ outlines: [OUTLINE] }));
    expect(await screen.findByText("Xây dựng API backend.")).toBeInTheDocument();
    expect(screen.getByText("Gợi ý của AI — chỉ để tham khảo")).toBeInTheDocument();
    expect(screen.getByText("Đề cương về backend.")).toBeInTheDocument();
    expect(screen.getByText("CLO2 — Triển khai")).toBeInTheDocument();
  });

  it("đề cương không có gợi ý AI → vẫn duyệt được, có thông báo không có gợi ý", async () => {
    setup(queue({ outlines: [{ ...OUTLINE, ai_summary: null }] }));
    expect(await screen.findByText("Không có gợi ý AI cho đề cương này.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yêu cầu chỉnh sửa" })).toBeInTheDocument();
  });

  it("từ chối đề cương: gửi nhận xét và version của đề cương", async () => {
    const user = setup(queue({ outlines: [OUTLINE] }));
    await user.type(await screen.findByRole("textbox"), "Thiếu kế hoạch kiểm thử");
    await user.click(screen.getByRole("button", { name: "Từ chối" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/outlines/7/decision",
      { decision: "rejected", reason: "Thiếu kế hoạch kiểm thử", version: 3 }));
  });

  it("thẻ gia hạn: lý do, hạn cũ → hạn mới, điều khoản liên quan; chỉ chấp nhận hoặc từ chối", async () => {
    setup(queue({ extensions: [EXTENSION] }));
    expect(await screen.findByText("Ốm 2 tuần")).toBeInTheDocument();
    expect(screen.getByText(/Xin gia hạn · Báo cáo giữa kỳ/)).toBeInTheDocument();
    expect(screen.getByText("Xin dời 14 ngày.")).toBeInTheDocument();
    expect(screen.getByText("Điều 10")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "mở file" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chấp nhận gia hạn" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yêu cầu chỉnh sửa" })).not.toBeInTheDocument();
  });

  it("chấp nhận gia hạn: POST tới endpoint gia hạn, không gửi version", async () => {
    const user = setup(queue({ extensions: [EXTENSION] }));
    await user.click(await screen.findByRole("button", { name: "Chấp nhận gia hạn" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/extensions/9/decision", { decision: "approved", reason: "" }));
  });

  it("không tự quyết định: tải hàng chờ xong vẫn chưa có POST nào", async () => {
    setup(queue({ internships: [INTERNSHIP], outlines: [OUTLINE], extensions: [EXTENSION] }));
    await screen.findByText("3 mục đang chờ bạn xử lý");
    expect(api.mock.calls.every((c) => c[0] === "GET")).toBe(true);
  });
});

describe("LecturerQueue — các nhánh hiển thị còn lại", () => {
  it("đề cương nhắc đủ mọi chuẩn đầu ra → ghi rõ, không liệt kê thiếu", async () => {
    setup(queue({ outlines: [{ ...OUTLINE, ai_summary: { ...OUTLINE.ai_summary, uncovered_outcomes: [] } }] }));
    expect(await screen.findByText("Đề cương có nhắc tới mọi chuẩn đầu ra học phần.")).toBeInTheDocument();
    expect(screen.queryByText(/chưa thấy nhắc tới/)).not.toBeInTheDocument();
  });

  it("hồ sơ thiếu trường hiện dấu gạch; hình thức toàn thời gian; ngày định dạng vi-VN", async () => {
    setup(queue({ internships: [{ ...INTERNSHIP, ai_fields: undefined, mode: "full_time", company_address: "" }] }));
    expect(await screen.findByText("Toàn thời gian")).toBeInTheDocument();
    expect(screen.getByText("5/1/2027")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.queryByText("AI điền")).not.toBeInTheDocument();
  });

  it("gia hạn không có minh chứng hay gợi ý AI vẫn duyệt được", async () => {
    setup(queue({ extensions: [{ ...EXTENSION, evidence_id: null, ai_summary: null }] }));
    expect(await screen.findByText("Ốm 2 tuần")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "mở file" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chấp nhận gia hạn" })).toBeInTheDocument();
  });

  it("lỗi khi ra quyết định → hiện lỗi và không tải lại hàng chờ", async () => {
    const user = setup(queue({ internships: [INTERNSHIP] }));
    api.mockImplementation(async (method, path) => { if (method === "POST") throw new Error("Phiên bản đã cũ"); return queue({ internships: [INTERNSHIP] }); });
    await user.click(await screen.findByRole("button", { name: "Duyệt" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Phiên bản đã cũ");
    expect(api.mock.calls.filter((c) => c[1] === "/approvals/queue")).toHaveLength(1);
  });
});
