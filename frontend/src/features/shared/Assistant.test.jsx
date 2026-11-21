import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Assistant from "./Assistant";

const chat = { messages: [], busy: false, ask: vi.fn() };
vi.mock("../../context/ChatContext", () => ({ useChat: () => chat }));

const setup = (over = {}) => {
  Object.assign(chat, { messages: [], busy: false }, over);
  render(<MemoryRouter><Assistant /></MemoryRouter>);
  return userEvent.setup();
};

beforeEach(() => {
  chat.ask = vi.fn();
});

describe("Assistant — giới thiệu và gợi ý", () => {
  it("nói rõ trợ lý chỉ trả lời theo quy định, luôn dẫn nguồn và không quyết định thay giảng viên", () => {
    setup();
    expect(screen.getByRole("heading", { name: "Trợ lý chính sách thực tập" })).toBeInTheDocument();
    expect(screen.getByText(/luôn dẫn nguồn/)).toBeInTheDocument();
    expect(screen.getByText(/không duyệt hay cam kết kết quả/)).toBeInTheDocument();
  });

  it("chưa có hội thoại → mời đặt câu hỏi", () => {
    setup();
    expect(screen.getByText("Hãy đặt câu hỏi về thủ tục, thời hạn hay quy định thực tập.")).toBeInTheDocument();
  });

  it("bấm câu hỏi gợi ý thì hỏi ngay đúng câu đó", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Khi nào phải nộp đề cương?" }));
    expect(chat.ask).toHaveBeenCalledWith("Khi nào phải nộp đề cương?");
  });
});

describe("Assistant — gửi câu hỏi", () => {
  it("nút Hỏi bị khóa khi ô trống hoặc chỉ có khoảng trắng", async () => {
    const user = setup();
    const button = screen.getByRole("button", { name: "Hỏi" });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Câu hỏi"), "   ");
    expect(button).toBeDisabled();
  });

  it("gửi câu hỏi đã cắt khoảng trắng rồi xóa ô nhập", async () => {
    const user = setup();
    const input = screen.getByLabelText("Câu hỏi");
    await user.type(input, "  Thực tập tối thiểu mấy tuần?  ");
    await user.click(screen.getByRole("button", { name: "Hỏi" }));
    expect(chat.ask).toHaveBeenCalledWith("Thực tập tối thiểu mấy tuần?");
    expect(input).toHaveValue("");
  });

  it("Enter trong ô nhập cũng gửi", async () => {
    const user = setup();
    await user.type(screen.getByLabelText("Câu hỏi"), "Có được gia hạn không?{Enter}");
    expect(chat.ask).toHaveBeenCalledWith("Có được gia hạn không?");
  });

  it("đang chờ trả lời thì khóa gợi ý và nút Hỏi, không gửi thêm", async () => {
    const user = setup({ busy: true });
    expect(screen.getByRole("button", { name: "Hỏi" })).toBeDisabled();
    const chip = screen.getByRole("button", { name: "Mỗi tuần cần bao nhiêu giờ?" });
    expect(chip).toBeDisabled();
    await user.type(screen.getByLabelText("Câu hỏi"), "abc{Enter}");
    expect(chat.ask).not.toHaveBeenCalled();
  });

  it("giới hạn độ dài câu hỏi 2000 ký tự", () => {
    setup();
    expect(screen.getByLabelText("Câu hỏi")).toHaveAttribute("maxlength", "2000");
  });
});

describe("Assistant — hiển thị hội thoại", () => {
  it("hiện câu hỏi của người dùng và câu trả lời của trợ lý", () => {
    setup({ messages: [{ role: "user", content: "Tối thiểu mấy tuần?" }, { role: "assistant", content: "Tối thiểu 8 tuần [1]." }] });
    expect(screen.getByText("Tối thiểu mấy tuần?")).toBeInTheDocument();
    expect(screen.getByText("Tối thiểu 8 tuần [1].")).toBeInTheDocument();
    expect(screen.queryByText("Hãy đặt câu hỏi về thủ tục, thời hạn hay quy định thực tập.")).not.toBeInTheDocument();
  });

  it("hiện trạng thái đang xử lý của câu trả lời chưa xong", () => {
    setup({ messages: [{ role: "assistant", content: "", status: "Đang tìm quy định…" }] });
    expect(screen.getByText("Đang tìm quy định…")).toBeInTheDocument();
  });

  it("mỗi nguồn trích dẫn là một mục xổ ra có nhãn và trích đoạn", async () => {
    const user = setup({
      messages: [{ role: "assistant", content: "Trả lời", citations: [
        { n: 1, label: "QĐ-TT/2026 · Điều 3 / Khoản 1", excerpt: "Thời gian thực tập tối thiểu 8 tuần." },
        { n: 2, label: "QĐ-TT/2026 · Điều 8", excerpt: "Nhật ký ghi hằng tuần." },
      ] }],
    });
    expect(screen.getByText("Nguồn")).toBeInTheDocument();
    await user.click(screen.getByText("[1] QĐ-TT/2026 · Điều 3 / Khoản 1"));
    expect(screen.getByText("Thời gian thực tập tối thiểu 8 tuần.")).toBeInTheDocument();
    expect(screen.getByText("[2] QĐ-TT/2026 · Điều 8")).toBeInTheDocument();
  });

  it("câu trả lời không có nguồn thì không hiện khối Nguồn", () => {
    setup({ messages: [{ role: "assistant", content: "Mình chỉ trả lời về quy định thực tập.", citations: [] }] });
    expect(screen.queryByText("Nguồn")).not.toBeInTheDocument();
  });

  it("chế độ trích nguyên văn có ghi chú không diễn giải; chế độ thường thì không", () => {
    setup({ messages: [
      { role: "assistant", content: "A", mode: "extractive_timeout" },
      { role: "assistant", content: "B", mode: "llm" },
    ] });
    expect(screen.getAllByText("Trích nguyên văn quy định (không diễn giải).")).toHaveLength(1);
  });

  it("câu hỏi gia hạn có link sang mục Mốc để tạo yêu cầu", () => {
    setup({ messages: [{ role: "assistant", content: "Bạn có thể xin gia hạn.", suggest: true }] });
    expect(screen.getByRole("link", { name: /tạo yêu cầu gia hạn/ })).toHaveAttribute("href", "/");
  });
});
