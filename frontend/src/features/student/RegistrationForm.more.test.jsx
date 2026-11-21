import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api, streamIntake } from "../../lib/api";
import RegistrationForm from "./RegistrationForm";

// Các trường hợp bổ sung cho RegistrationForm: tiến trình, khung xem nguồn, tô lỗi theo trường, lưu thất bại.

vi.mock("../../lib/api", () => ({ api: vi.fn(), streamIntake: vi.fn() }));

const INTERNSHIP = { id: 5, version: 3, ai_fields: ["position"], position: "Backend" };
const TEXT = "Mã số thuế: 0101234567";

const RESULT = {
  label: "Gợi ý của AI",
  source: "rules",
  matched_company: { name: "Công ty Sao Mai" },
  document: { text: TEXT, pages: [{ index: 0, image: "data:image/png;base64,AAA", width: 100, height: 100 }] },
  fields: {
    company_tax_code: {
      value: "0101234567", raw: "0101234567", confidence: 0.9, by: "rules",
      source: { spans: [[TEXT.indexOf("0101"), TEXT.length]], boxes: [{ page: 0, x: 0.1, y: 0.1, w: 0.2, h: 0.05 }] },
    },
    start_date: { value: null, confidence: 0.2, needs_manual: true, raw: "35/13/2027", by: "rules" },
    mentor_name: { value: null, confidence: 0.2, needs_manual: true, unverified: "Ông Bảo", by: "llm" },
    mentor_email: { value: "bao@saomai.vn", confidence: 0.75, by: "rules" },
    not_a_form_field: { value: "bỏ qua", confidence: 0.5, by: "rules" },
  },
};

const setup = (props = {}) => {
  const reload = vi.fn();
  const utils = render(
    <ToastProvider>
      <RegistrationForm internship={INTERNSHIP} editable status={<span>Nháp</span>} reload={reload} {...props} />
    </ToastProvider>,
  );
  return { reload, user: userEvent.setup(), ...utils };
};

const pick = (container, file = new File(["x"], "giay.pdf")) => {
  const input = container.querySelector('input[type="file"]');
  fireEvent.change(input, { target: { files: file ? [file] : [] } });
  return input;
};

const withResult = (result = RESULT) => streamIntake.mockImplementation(async (_f, onEvent) => onEvent({ type: "done", result }));

beforeEach(() => {
  api.mockReset();
  streamIntake.mockReset();
});

describe("tiến trình xử lý file", () => {
  it("hiện tiến trình khi đang xử lý, cập nhật theo sự kiện stage, rồi ẩn khi xong", async () => {
    let emit; let finish;
    streamIntake.mockImplementation((_f, onEvent) => new Promise((resolve) => { emit = onEvent; finish = resolve; }));
    const { container } = setup();
    pick(container, new File(["x"], "scan.png"));
    expect(await screen.findByText("Đang tải file lên…")).toBeInTheDocument();
    expect(screen.getByText(/scan\.png/)).toBeInTheDocument();

    act(() => emit({ type: "stage", stage: "ocr", label: "Đang nhận dạng chữ", page: 1, pages: 2 }));
    expect(screen.getByText("Đang nhận dạng chữ")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");

    act(() => { emit({ type: "done", result: RESULT }); finish(); });
    await screen.findByRole("table");
    expect(screen.queryByText("Đang nhận dạng chữ")).not.toBeInTheDocument();
  });

  it("lỗi giữa chừng cũng tắt tiến trình", async () => {
    streamIntake.mockImplementation(async () => { throw new Error("Mất mạng"); });
    const { container } = setup();
    pick(container);
    expect(await screen.findByText("Mất mạng")).toBeInTheDocument();
    expect(screen.queryByText("Đang tải file lên…")).not.toBeInTheDocument();
  });

  it("bỏ chọn file (không có file) thì không gọi backend", () => {
    const { container } = setup();
    pick(container, null);
    expect(streamIntake).not.toHaveBeenCalled();
  });

  it("sau khi chọn, input được reset để chọn lại đúng file đó", async () => {
    withResult();
    const { container } = setup();
    const input = pick(container);
    await screen.findByRole("table");
    expect(input.value).toBe("");
  });

  it("chọn file mới thì thay kết quả cũ", async () => {
    withResult();
    const { container } = setup();
    pick(container);
    await screen.findByRole("table");
    streamIntake.mockImplementation(async (_f, onEvent) => onEvent({ type: "error", detail: "File lỗi" }));
    pick(container, new File(["y"], "khac.pdf"));
    expect(await screen.findByText("File lỗi")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument(); // lỗi thay hẳn kết quả cũ, không để gợi ý cũ lẫn với file mới
  });
});

describe("bảng gợi ý", () => {
  it("nhãn nguồn và doanh nghiệp đã có; mức tin cậy làm tròn", async () => {
    withResult();
    const { container } = setup();
    pick(container);
    expect(await screen.findByText(/nguồn: bộ trích xuất theo luật · khớp DN đã có: Công ty Sao Mai/)).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("badge Theo luật/AI; trường AI đề xuất nhưng không thấy trong file thì không dùng", async () => {
    withResult();
    const { container } = setup();
    pick(container);
    const table = await screen.findByRole("table");
    expect(within(table).getAllByText("Theo luật").length).toBeGreaterThan(0);
    expect(within(table).getByText(/AI đề xuất “Ông Bảo” nhưng không thấy trong file nên không dùng/)).toBeInTheDocument();
    expect(within(table).getByText(/đọc được: “35\/13\/2027” \(không hợp lệ\)/)).toBeInTheDocument();
  });

  it("cột vị trí: có nút xem, hoặc nêu lý do không có", async () => {
    withResult();
    const { container } = setup();
    pick(container);
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("button", { name: "Xem trong file" })).toHaveLength(1);
    expect(within(table).getByText("không xác định được vị trí")).toBeInTheDocument(); // start_date: có raw, không có source
    expect(within(table).getAllByText("không tìm thấy trong file").length).toBeGreaterThan(0);
  });

  it("không có document → không có cột vị trí và khung xem nguồn", async () => {
    withResult({ ...RESULT, document: undefined });
    const { container } = setup();
    pick(container);
    const table = await screen.findByRole("table");
    expect(within(table).queryByText("Vị trí trong file")).not.toBeInTheDocument();
    expect(screen.queryByText("File bạn đã tải lên")).not.toBeInTheDocument();
  });

  it("Xem trong file: chọn dòng, đánh dấu aria-pressed và sáng khung tương ứng trên ảnh", async () => {
    withResult();
    const { container, user } = setup();
    pick(container);
    const btn = await screen.findByRole("button", { name: "Xem trong file" });
    expect(btn).toHaveAttribute("aria-pressed", "false");
    await user.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "true");
    expect(btn.closest("tr")).toHaveClass("is-active");
    expect(screen.getByRole("button", { name: /Mã số thuế: 0101234567/ })).toHaveClass("is-active");
  });

  it("bấm khung trên ảnh cũng chọn trường (đồng bộ với bảng)", async () => {
    withResult();
    const { container, user } = setup();
    pick(container);
    await screen.findByRole("table");
    await user.click(screen.getByRole("button", { name: /Mã số thuế: 0101234567/ }));
    expect(screen.getByRole("button", { name: "Xem trong file" })).toHaveAttribute("aria-pressed", "true");
  });

  it("Điền vào form bỏ qua trường không có trong form và không đụng trường cần nhập tay", async () => {
    withResult();
    const { container, user } = setup();
    pick(container);
    await user.click(await screen.findByRole("button", { name: "Điền vào form" }));
    expect(screen.getByLabelText(/Mã số thuế/, { selector: "input" })).toHaveValue("0101234567");
    expect(screen.getByLabelText(/Email người hướng dẫn/)).toHaveValue("bao@saomai.vn");
    expect(screen.getByLabelText(/Ngày bắt đầu/)).toHaveValue("");
    expect(screen.getByLabelText(/Người hướng dẫn tại DN/)).toHaveValue("");
    expect(await screen.findByRole("status")).toHaveTextContent("Đã điền gợi ý");
  });
});

describe("dấu AI và lưu", () => {
  it("trường AI đã lưu từ trước (ai_fields) vẫn có dấu AI và nhắc kiểm tra", () => {
    setup();
    expect(screen.getByLabelText(/Vị trí thực tập/).closest(".field")).toHaveClass("is-ai");
    expect(screen.getByText(/do AI gợi ý — hãy kiểm tra trước khi nộp/)).toBeInTheDocument();
  });

  it("chỉ gửi các trường còn dấu AI khi lưu", async () => {
    api.mockResolvedValue({ version: 4 });
    const { user } = setup();
    await user.type(screen.getByLabelText(/Vị trí thực tập/), "!"); // sửa tay → bỏ dấu AI
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(api.mock.calls[0][2]).toMatchObject({ position: "Backend!", ai_fields: [] });
  });

  it("sau khi lưu thì dùng version mới cho lần lưu kế tiếp (khóa lạc quan)", async () => {
    api.mockResolvedValueOnce({ version: 4 }).mockResolvedValueOnce({ version: 5 });
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    expect(api.mock.calls.map((c) => c[2].version)).toEqual([3, 4]);
  });

  it("đổi hình thức làm việc được lưu", async () => {
    api.mockResolvedValue({ version: 4 });
    const { user } = setup();
    await user.selectOptions(screen.getByLabelText(/Hình thức/), "part_time");
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await waitFor(() => expect(api.mock.calls[0][2].mode).toBe("part_time"));
  });

  it("cắt khoảng trắng đầu/cuối khi lưu", async () => {
    api.mockResolvedValue({ version: 4 });
    const { user } = setup();
    await user.type(screen.getByLabelText(/Tên doanh nghiệp/), "  Công ty B  ");
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await waitFor(() => expect(api.mock.calls[0][2].company_name).toBe("Công ty B"));
  });

  it("lưu nháp thất bại (vd. version cũ) → hiện lỗi, không gọi bước sau", async () => {
    api.mockRejectedValue(new Error("Hồ sơ đã được sửa ở nơi khác"));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Hồ sơ đã được sửa ở nơi khác");
    expect(api).toHaveBeenCalledTimes(1);
  });

  it("kiểm tra theo quy chế: lưu thất bại → dừng, không gọi validate", async () => {
    api.mockRejectedValue(new Error("Lỗi lưu"));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Lỗi lưu");
    expect(api).toHaveBeenCalledTimes(1);
  });

  it("nộp hồ sơ: lưu thất bại → dừng, không submit, không reload", async () => {
    api.mockRejectedValue(new Error("Lỗi lưu"));
    const { user, reload } = setup();
    await user.click(screen.getByRole("button", { name: "Xác nhận & nộp hồ sơ" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Lỗi lưu");
    expect(api).toHaveBeenCalledTimes(1);
    expect(reload).not.toHaveBeenCalled();
  });

  it("nộp hồ sơ: lỗi khác (không phải danh sách vi phạm) → hiện thông báo lỗi", async () => {
    api.mockImplementation(async (m, path) => { if (path.endsWith("/submit")) throw new Error("Hết hạn đăng ký"); return { version: 4 }; });
    const { user, reload } = setup();
    await user.click(screen.getByRole("button", { name: "Xác nhận & nộp hồ sơ" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Hết hạn đăng ký");
    expect(reload).not.toHaveBeenCalled();
  });
});

describe("kết quả kiểm tra quy chế", () => {
  it("tô lỗi đúng ô theo tên trường trong thông báo, kèm căn cứ", async () => {
    api.mockImplementation(async (m, path) => (path.endsWith("/validate")
      ? { results: [{ passed: false, message: "Thiếu mã số thuế", citation: { doc: "Quy chế TT", path: "Điều 5" } }, { passed: true }] }
      : { version: 4 }));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    expect(await screen.findByText("Thiếu mã số thuế")).toBeInTheDocument();
    expect(screen.getByText(/Căn cứ: Quy chế TT · Điều 5/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Mã số thuế/).closest(".field")).toHaveClass("has-error");
    expect(screen.getByLabelText(/Tên doanh nghiệp/).closest(".field")).not.toHaveClass("has-error");
  });

  it("kết quả thiếu cờ passed vẫn tính là không đạt", async () => {
    api.mockImplementation(async (m, path) => (path.endsWith("/validate") ? { results: [{ message: "Chưa rõ" }] } : { version: 4 }));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    expect(await screen.findByText("Chưa rõ")).toBeInTheDocument();
    expect(screen.queryByText("Hồ sơ đạt mọi kiểm tra của quy chế")).not.toBeInTheDocument();
  });

  it("kiểm tra lại sau khi sửa thì kết quả cũ được thay", async () => {
    let ok = false;
    api.mockImplementation(async (m, path) => (path.endsWith("/validate")
      ? { results: [{ passed: ok, message: "Thiếu mã số thuế" }] } : { version: 4 }));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    await screen.findByText("Thiếu mã số thuế");
    ok = true;
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    expect(await screen.findByText("Hồ sơ đạt mọi kiểm tra của quy chế")).toBeInTheDocument();
    expect(screen.queryByText("Thiếu mã số thuế")).not.toBeInTheDocument();
  });
});
