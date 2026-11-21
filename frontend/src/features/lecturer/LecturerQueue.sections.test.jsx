import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import LecturerQueue from "./LecturerQueue";

// Các mục hàng chờ do nhóm 2 thêm (mốc đã nộp, nhật ký tuần) và phần chia mục có tiêu đề.
// Thẻ hồ sơ / đề cương / gia hạn nằm ở LecturerQueue.test.jsx.

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

const INTERNSHIP = { id: 1, version: 2, status: "submitted", student: { full_name: "Nguyễn Văn An" }, ai_fields: [] };
const OUTLINE = { id: 7, version: 3, internship: { student: { full_name: "Trần Thị Bình" } }, content: "Đề cương A", ai_summary: null };
const EXTENSION = {
  id: 9, student: { full_name: "Lê Văn Cường" }, milestone: { name: "Mốc B" }, reason: "Ốm",
  previous_due_date: "2027-02-01", requested_due_date: "2027-02-15", evidence_id: null, ai_summary: null,
};
const MILESTONE = {
  id: 11, internship_id: 3, name: "Báo cáo giữa kỳ", student: { full_name: "Phạm Thị Dung" }, due_date: "2027-02-01",
  submitted_at: "2027-01-30T09:15:00", missing_evidence: [],
  evidence: [{ id: 21, filename: "bao-cao.pdf", uploaded_at: "2027-01-30T09:10:00" }],
};
const LOG = {
  id: 31, internship_id: 3, week_no: 4, hours: 22, student: { full_name: "Hoàng Văn Em" },
  content: "Viết kiểm thử tích hợp", difficulties: "Thiếu dữ liệu mẫu",
  attachments: [{ id: 41, filename: "anh-man-hinh.png", uploaded_at: "2027-01-31T10:00:00" }],
};

const queue = (over = {}) => ({ internships: [], outlines: [], milestones: [], extensions: [], exceptions: [], logs: [], ...over });

const setup = (data) => {
  api.mockImplementation(async (method, path) => (path === "/approvals/queue" ? data : {}));
  render(
    <ToastProvider>
      <MemoryRouter><LecturerQueue /></MemoryRouter>
    </ToastProvider>,
  );
  return userEvent.setup();
};

const queueReads = () => api.mock.calls.filter((c) => c[1] === "/approvals/queue").length;

beforeEach(() => {
  localStorage.clear();
  api.mockReset();
});

const byType = async (user) => user.click(await screen.findByRole("button", { name: "Theo loại" }));
const names = () => screen.getAllByText(/^(Nguyễn Văn An|Trần Thị Bình|Lê Văn Cường|Phạm Thị Dung|Hoàng Văn Em)$/).map((n) => n.textContent);
const prio = (score, since, reasons = [], level = "low") => ({ score, since, reasons, level });

describe("LecturerQueue — chia mục (chế độ Theo loại)", () => {
  it("mỗi mục có tiêu đề kèm số lượng; mục rỗng thì ẩn; đếm cả mốc và nhật ký", async () => {
    const user = setup(queue({ internships: [INTERNSHIP], milestones: [MILESTONE], logs: [LOG, { ...LOG, id: 32 }] }));
    expect(await screen.findByText("4 mục đang chờ bạn xử lý")).toBeInTheDocument();
    await byType(user);
    expect(screen.getByRole("region", { name: "Hồ sơ đăng ký" })).toHaveTextContent("(1)");
    expect(screen.getByRole("region", { name: "Mốc đã nộp" })).toHaveTextContent("(1)");
    expect(screen.getByRole("region", { name: "Nhật ký tuần" })).toHaveTextContent("(2)");
    expect(screen.queryByRole("region", { name: "Đề cương" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Xin gia hạn" })).not.toBeInTheDocument();
  });

  it("thứ tự các mục: hồ sơ, đề cương, mốc, gia hạn, nhật ký", async () => {
    const user = setup(queue({ internships: [INTERNSHIP], outlines: [OUTLINE], milestones: [MILESTONE], extensions: [EXTENSION], logs: [LOG] }));
    await screen.findByText("5 mục đang chờ bạn xử lý");
    await byType(user);
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label")))
      .toEqual(["Hồ sơ đăng ký", "Đề cương", "Mốc đã nộp", "Xin gia hạn", "Nhật ký tuần"]);
  });

  it("phản hồi thiếu trường milestones/logs (API cũ) vẫn hiển thị bình thường", async () => {
    setup({ internships: [INTERNSHIP], outlines: [], extensions: [] });
    expect(await screen.findByText("1 mục đang chờ bạn xử lý")).toBeInTheDocument();
  });
});

describe("LecturerQueue — sắp xếp theo ưu tiên", () => {
  const data = () => queue({
    internships: [{ ...INTERNSHIP, priority: prio(10, "2027-01-05T00:00:00") }],
    milestones: [{ ...MILESTONE, priority: prio(90, "2027-01-03T00:00:00", ["Trễ hạn"], "high") }],
    logs: [{ ...LOG, priority: prio(40, "2027-01-01T00:00:00", [], "medium") }],
  });

  it("mặc định là Ưu tiên: điểm cao lên trước, không chia mục", async () => {
    setup(data());
    await screen.findByText("3 mục đang chờ bạn xử lý");
    expect(names()).toEqual(["Phạm Thị Dung", "Hoàng Văn Em", "Nguyễn Văn An"]);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ưu tiên" })).toHaveAttribute("aria-pressed", "true");
  });

  it("Chờ lâu nhất: sắp theo thời điểm bắt đầu chờ", async () => {
    const user = setup(data());
    await user.click(await screen.findByRole("button", { name: "Chờ lâu nhất" }));
    expect(names()).toEqual(["Hoàng Văn Em", "Phạm Thị Dung", "Nguyễn Văn An"]);
  });

  it("điểm bằng nhau thì mục chờ lâu hơn lên trước; mục thiếu priority xuống cuối", async () => {
    setup(queue({
      internships: [{ ...INTERNSHIP, priority: prio(5, "2027-01-09T00:00:00") }],
      milestones: [{ ...MILESTONE, priority: prio(5, "2027-01-02T00:00:00") }],
      logs: [LOG],
    }));
    await screen.findByText("3 mục đang chờ bạn xử lý");
    expect(names()).toEqual(["Phạm Thị Dung", "Nguyễn Văn An", "Hoàng Văn Em"]);
  });

  it("hiện nhãn mức ưu tiên và lý do; mức thấp không lý do thì không hiện dòng", async () => {
    setup(data());
    await screen.findByText("3 mục đang chờ bạn xử lý");
    expect(screen.getByText("Ưu tiên cao")).toBeInTheDocument();
    expect(screen.getByText("Ưu tiên vừa")).toBeInTheDocument();
    expect(screen.getByText("Trễ hạn")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Lý do ưu tiên")).toHaveLength(2);
  });

  it("nhớ lựa chọn sắp xếp cho lần mở sau; giá trị lạ trong storage bị bỏ qua", async () => {
    const user = setup(data());
    await user.click(await screen.findByRole("button", { name: "Theo loại" }));
    expect(localStorage.getItem("vin15_queue_sort")).toBe("type");
    cleanup();
    setup(data());
    expect(await screen.findByRole("button", { name: "Theo loại" })).toHaveAttribute("aria-pressed", "true");
    cleanup();
    localStorage.setItem("vin15_queue_sort", "bậy");
    setup(data());
    expect(await screen.findByRole("button", { name: "Ưu tiên" })).toHaveAttribute("aria-pressed", "true");
  });

  it("chỉ có 1 mục thì không hiện nút sắp xếp", async () => {
    setup(queue({ internships: [INTERNSHIP] }));
    await screen.findByText("1 mục đang chờ bạn xử lý");
    expect(screen.queryByRole("group", { name: "Sắp xếp hàng chờ" })).not.toBeInTheDocument();
  });
});

describe("LecturerQueue — thẻ mốc đã nộp", () => {
  it("hiện tên mốc, hạn, thời điểm nộp, file minh chứng và liên kết tới hồ sơ", async () => {
    setup(queue({ milestones: [MILESTONE] }));
    expect(await screen.findByText("Phạm Thị Dung")).toBeInTheDocument();
    expect(screen.getByText("Mốc: Báo cáo giữa kỳ")).toBeInTheDocument();
    expect(screen.getByText(/Hạn 1\/2\/2027 · nộp lúc/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "bao-cao.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Xem hồ sơ →" })).toHaveAttribute("href", "/internship/3");
    expect(screen.queryByText("Thiếu minh chứng bắt buộc")).not.toBeInTheDocument();
  });

  it("thiếu minh chứng bắt buộc → cảnh báo liệt kê loại còn thiếu", async () => {
    setup(queue({ milestones: [{ ...MILESTONE, evidence: [], missing_evidence: ["Báo cáo", "Xác nhận DN"] }] }));
    expect(await screen.findByText("Thiếu minh chứng bắt buộc")).toBeInTheDocument();
    expect(screen.getByText("Báo cáo, Xác nhận DN")).toBeInTheDocument();
    expect(screen.getByText("Chưa có file minh chứng.")).toBeInTheDocument();
  });

  it("chưa có thời điểm nộp thì không ghi nộp lúc", async () => {
    setup(queue({ milestones: [{ ...MILESTONE, submitted_at: null }] }));
    expect(await screen.findByText(/^Hạn 1\/2\/2027$/)).toBeInTheDocument();
  });

  it("chấp nhận mốc: POST kèm nhận xét tới /milestones/{id}/review rồi tải lại hàng chờ", async () => {
    const user = setup(queue({ milestones: [MILESTONE] }));
    await user.type(await screen.findByLabelText("Nhận xét"), "Đạt");
    await user.click(screen.getByRole("button", { name: "Chấp nhận" }));
    await waitFor(() => expect(queueReads()).toBe(2));
    expect(api).toHaveBeenCalledWith("POST", "/milestones/11/review", { decision: "accepted", comment: "Đạt" });
  });

  it("trả lại mốc: decision là rejected", async () => {
    const user = setup(queue({ milestones: [MILESTONE] }));
    await user.click(await screen.findByRole("button", { name: "Trả lại" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/milestones/11/review", { decision: "rejected", comment: "" }));
  });
});

describe("LecturerQueue — thẻ nhật ký tuần", () => {
  it("hiện tuần, số giờ, nội dung, khó khăn, file đính kèm và liên kết tới hồ sơ", async () => {
    setup(queue({ logs: [LOG] }));
    expect(await screen.findByText("Hoàng Văn Em")).toBeInTheDocument();
    expect(screen.getByText("Nhật ký tuần 4 · 22 giờ")).toBeInTheDocument();
    expect(screen.getByText("Viết kiểm thử tích hợp")).toBeInTheDocument();
    expect(screen.getByText("Khó khăn: Thiếu dữ liệu mẫu")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "anh-man-hinh.png" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Xem hồ sơ →" })).toHaveAttribute("href", "/internship/3");
  });

  it("không có khó khăn hoặc file đính kèm thì không hiện các phần đó", async () => {
    setup(queue({ logs: [{ ...LOG, difficulties: "", attachments: [] }] }));
    await screen.findByText("Viết kiểm thử tích hợp");
    expect(screen.queryByText(/Khó khăn:/)).not.toBeInTheDocument();
    expect(screen.queryByText("Chưa có file minh chứng.")).not.toBeInTheDocument();
  });

  it("trả lại nhật ký dùng decision returned; chấp nhận dùng accepted", async () => {
    const user = setup(queue({ logs: [LOG] }));
    await user.click(await screen.findByRole("button", { name: "Trả lại" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/logs/31/review", { decision: "returned", comment: "" }));
    await user.click(screen.getByRole("button", { name: "Chấp nhận" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/logs/31/review", { decision: "accepted", comment: "" }));
  });

  it("lỗi khi duyệt nhật ký → hiện lỗi, không tải lại hàng chờ", async () => {
    const user = setup(queue({ logs: [LOG] }));
    api.mockImplementation(async (method) => {
      if (method === "POST") throw new Error("Nhật ký đã được duyệt");
      return queue({ logs: [LOG] });
    });
    await user.click(await screen.findByRole("button", { name: "Chấp nhận" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Nhật ký đã được duyệt");
    expect(queueReads()).toBe(1);
  });
});

describe("LecturerQueue — ngoại lệ", () => {
  const EXCEPTION = {
    id: 5, kind: "credit_recognition", student: { full_name: "Vũ Thị Hoa" }, reason: "Đề nghị quy đổi tín chỉ",
    payload: { credits: 4, basis: "" }, milestone: null, evidence_id: null,
    ai_summary: { label: "Gợi ý của AI", summary: "Tóm tắt yêu cầu", related_clauses: [] },
  };

  it("hiện thẻ ngoại lệ kèm gợi ý AI và chỉ có nút Chấp nhận / Từ chối ngoại lệ", async () => {
    setup(queue({ exceptions: [EXCEPTION] }));
    expect(await screen.findByText("Vũ Thị Hoa")).toBeInTheDocument();
    expect(screen.getByText("Tóm tắt yêu cầu")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chấp nhận ngoại lệ" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yêu cầu chỉnh sửa" })).not.toBeInTheDocument();
  });
});
