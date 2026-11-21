import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { EvidenceLink } from "./EvidenceLink";
import { EvidencePreview } from "./EvidencePreview";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
let role = "lecturer";
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ me: { role } }) }));

const preview = (over = {}) => ({ filename: "bao-cao.pdf", size: 2048, kind: "pdf", url: "/files/5?sig=abc", ...over });
const review = (over = {}) => ({
  label: "Gợi ý của AI — chỉ để tham khảo", summary: "Báo cáo nêu quá trình thực tập 8 tuần.", warnings: [],
  checklist: [], checklist_citation: null, evidence_label: "Báo cáo cuối kỳ", uncovered_outcomes: [],
  limits: "AI có thể sai.", used_ocr: false, unavailable: false, ...over,
});

/** `p` là phản hồi preview; `r` là phản hồi review (hoặc Error để mô phỏng AI lỗi). */
const setup = ({ p = preview(), r = review(), onClose = vi.fn() } = {}) => {
  api.mockImplementation(async (method, path) => {
    if (path === "/evidence/5/preview") { if (p instanceof Error) throw p; return p; }
    if (path === "/evidence/5/review") { if (r instanceof Error) throw r; return r; }
    if (path === "/evidence/5/url") return { url: "/files/5?download=1" };
    return {};
  });
  render(<ToastProvider><EvidencePreview id={5} onClose={onClose} /></ToastProvider>);
  return { onClose, user: userEvent.setup() };
};

beforeEach(() => {
  api.mockReset();
  role = "lecturer";
});
afterEach(() => {
  document.body.style.overflow = "";
});

describe("EvidencePreview — theo loại file", () => {
  it("PDF: nhúng iframe, có link mở tab mới, hiện tên và dung lượng", async () => {
    setup();
    expect(await screen.findByTitle("bao-cao.pdf")).toHaveAttribute("src", "/files/5?sig=abc");
    expect(screen.getByText("2 KB")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mở tab mới" })).toHaveAttribute("href", "/files/5?sig=abc");
  });

  it("ảnh: hiện thẻ img có alt là tên file", async () => {
    setup({ p: preview({ filename: "anh.png", kind: "image", url: "/files/5.png" }) });
    expect(await screen.findByAltText("anh.png")).toHaveAttribute("src", "/files/5.png");
    expect(screen.queryByRole("link", { name: "Mở tab mới" })).not.toBeInTheDocument();
  });

  it("Word: hiện phần chữ đã trích, nói rõ là bản xem nhanh và có ghi khi bị cắt bớt", async () => {
    setup({ p: preview({ filename: "bao-cao.docx", kind: "text", text: "Nội dung báo cáo", truncated: true }) });
    expect(await screen.findByText("Nội dung báo cáo")).toBeInTheDocument();
    expect(screen.getByText(/chỉ gồm phần chữ của file Word \(đã cắt bớt\)/)).toBeInTheDocument();
  });

  it("định dạng không xem được → nhắc tải về", async () => {
    setup({ p: preview({ kind: "none" }) });
    expect(await screen.findByText(/không xem trực tiếp được/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tải về" })).toBeInTheDocument();
  });

  it("PDF hỏng → nêu lý do cụ thể từ máy chủ", async () => {
    setup({ p: preview({ kind: "broken", problem: "File PDF không có trang nào" }) });
    expect(await screen.findByText(/File PDF không có trang nào/)).toBeInTheDocument();
  });

  it("file không còn trên máy chủ → báo nộp lại và không có nút Tải về", async () => {
    setup({ p: preview({ kind: "missing" }) });
    expect(await screen.findByText(/File không còn trên máy chủ/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tải về" })).not.toBeInTheDocument();
  });

  it("không tải được preview → hiện lỗi", async () => {
    setup({ p: new Error("Không có quyền xem file này") });
    expect(await screen.findByText("Không có quyền xem file này")).toBeInTheDocument();
  });

  it("dung lượng lớn hiển thị theo MB", async () => {
    setup({ p: preview({ size: 3 * 1024 * 1024 }) });
    expect(await screen.findByText("3.0 MB")).toBeInTheDocument();
  });
});

describe("EvidencePreview — đóng và tải về", () => {
  it("nút Đóng, phím Esc và bấm ra ngoài đều gọi onClose", async () => {
    const { user, onClose } = setup();
    await screen.findByTitle("bao-cao.pdf");
    await user.click(screen.getByRole("button", { name: "Đóng" }));
    await user.keyboard("{Escape}");
    await user.pointer({ keys: "[MouseLeft]", target: document.querySelector(".preview-overlay") });
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("bấm vào bên trong hộp xem không đóng", async () => {
    const { user, onClose } = setup();
    await user.click(await screen.findByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("mở thì khóa cuộn trang, đóng thì mở lại", async () => {
    api.mockResolvedValue({});
    const { unmount } = render(<ToastProvider><EvidencePreview id={5} onClose={() => {}} /></ToastProvider>);
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).toBe("");
  });

  it("Tải về: lấy link ký mới rồi chuyển hướng tới link đó", async () => {
    const assign = vi.fn();
    const original = window.location;
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, assign } });
    try {
      const { user } = setup();
      await user.click(await screen.findByRole("button", { name: "Tải về" }));
      await waitFor(() => expect(assign).toHaveBeenCalledWith("/files/5?download=1"));
      expect(api).toHaveBeenCalledWith("GET", "/evidence/5/url");
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: original });
    }
  });
});

describe("EvidencePreview — gợi ý AI", () => {
  it("sinh viên không thấy gợi ý AI và không gọi API review", async () => {
    role = "student";
    setup();
    await screen.findByTitle("bao-cao.pdf");
    expect(screen.queryByLabelText("Gợi ý AI đọc minh chứng")).not.toBeInTheDocument();
    expect(api).not.toHaveBeenCalledWith("GET", "/evidence/5/review");
  });

  it.each(["lecturer", "admin"])("%s thấy tóm tắt kèm nhãn AI và giới hạn", async (who) => {
    role = who;
    setup({ r: review({ used_ocr: true }) });
    expect(await screen.findByText("Gợi ý của AI — chỉ để tham khảo")).toBeInTheDocument();
    expect(screen.getByText("Báo cáo nêu quá trình thực tập 8 tuần.")).toBeInTheDocument();
    expect(screen.getByText(/AI có thể sai\. Chữ được đọc bằng OCR nên có thể sai\./)).toBeInTheDocument();
  });

  it("hiện cảnh báo, checklist có/chưa thấy, căn cứ và chuẩn đầu ra chưa nhắc tới", async () => {
    setup({
      r: review({
        warnings: ["Chưa thấy chữ ký doanh nghiệp"],
        checklist: [{ item: "Có chữ ký", found: false }, { item: "Có dấu mộc", found: true }],
        checklist_citation: { doc: "QĐ-TT/2026", path: "Điều 9" },
        uncovered_outcomes: [{ code: "CLO3" }, { code: "CLO5" }],
      }),
    });
    expect(await screen.findByText("Chưa thấy chữ ký doanh nghiệp")).toBeInTheDocument();
    expect(screen.getByText("Checklist: Báo cáo cuối kỳ")).toBeInTheDocument();
    expect(screen.getByText("Có chữ ký").closest("li")).toHaveClass("is-missing");
    expect(screen.getByText("Có dấu mộc").closest("li")).toHaveClass("is-found");
    expect(screen.getByText("Căn cứ: QĐ-TT/2026 · Điều 9")).toBeInTheDocument();
    expect(screen.getByText("Chuẩn đầu ra chưa thấy nhắc tới: CLO3, CLO5")).toBeInTheDocument();
  });

  it("AI báo không dùng được → nói vẫn duyệt bình thường", async () => {
    setup({ r: review({ unavailable: true }) });
    expect(await screen.findByText(/Chưa có gợi ý AI cho file này\. Bạn vẫn xem file và duyệt bình thường\./)).toBeInTheDocument();
    expect(screen.queryByText("Báo cáo nêu quá trình thực tập 8 tuần.")).not.toBeInTheDocument();
  });

  it("AI lỗi → cùng thông báo dự phòng, file vẫn xem được", async () => {
    setup({ r: new Error("AI timeout") });
    expect(await screen.findByText(/Chưa có gợi ý AI cho file này/)).toBeInTheDocument();
    expect(await screen.findByTitle("bao-cao.pdf")).toBeInTheDocument();
  });
});

describe("EvidenceLink", () => {
  it("hiện nút tên file; bấm mở cửa sổ xem, đóng thì ẩn", async () => {
    api.mockImplementation(async (_m, path) => (path.endsWith("/preview") ? preview() : review()));
    const user = userEvent.setup();
    render(<ToastProvider><EvidenceLink id={5}>bao-cao.pdf</EvidenceLink></ToastProvider>);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "bao-cao.pdf" }));
    expect(await screen.findByRole("dialog", { name: "Xem bao-cao.pdf" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Đóng" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
