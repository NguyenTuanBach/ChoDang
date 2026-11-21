import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api, streamIntake } from "../../lib/api";
import RegistrationForm from "./RegistrationForm";

vi.mock("../../lib/api", () => ({ api: vi.fn(), streamIntake: vi.fn() }));

const INTERNSHIP = { id: 5, version: 3, company_name: "Công ty A", mode: "part_time", ai_fields: [] };

// Kết quả /intake/extract: MST đọc được, SĐT không hợp lệ (cần nhập tay), tên DN do LLM bổ sung
const RESULT = {
  label: "Gợi ý của AI — hãy kiểm tra",
  source: "rules+llm",
  fields: {
    company_name: { value: "Công ty TNHH Sao Mai", confidence: 0.85, by: "llm" },
    company_tax_code: { value: "0101234567", confidence: 0.9, by: "rules" },
    mentor_phone: { value: null, confidence: 0.3, needs_manual: true, raw: "09l2 34", by: "rules" },
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

const uploadFile = (container, name = "giay.pdf") => {
  const input = container.querySelector('input[type="file"]');
  fireEvent.change(input, { target: { files: [new File(["x"], name, { type: "application/pdf" })] } });
};

const streamWith = (...events) => streamIntake.mockImplementation(async (_file, onEvent) => { events.forEach(onEvent); });

beforeEach(() => {
  api.mockReset();
  streamIntake.mockReset();
});

describe("RegistrationForm — hiển thị", () => {
  it("điền sẵn giá trị đã lưu; hình thức lấy từ hồ sơ", () => {
    setup();
    expect(screen.getByLabelText(/Tên doanh nghiệp/)).toHaveValue("Công ty A");
    expect(screen.getByLabelText(/Hình thức/)).toHaveValue("part_time");
  });

  it("không sửa được (đã nộp): ô bị khóa, không có nút nộp hay upload", () => {
    setup({ editable: false });
    expect(screen.getByLabelText(/Tên doanh nghiệp/)).toBeDisabled();
    expect(screen.queryByRole("button", { name: /Xác nhận & nộp hồ sơ/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Điền từ file/ })).not.toBeInTheDocument();
  });
});

describe("RegistrationForm — AI trích xuất", () => {
  it("hiện bảng gợi ý kèm độ tin cậy; trường không hợp lệ ghi cần nhập tay", async () => {
    streamWith({ type: "done", result: RESULT });
    const { container } = setup();
    uploadFile(container);
    const table = await screen.findByRole("table");
    expect(within(table).getByText("0101234567")).toBeInTheDocument();
    expect(within(table).getByText("90%")).toBeInTheDocument();
    expect(within(table).getByText("cần nhập tay")).toBeInTheDocument();
    expect(within(table).getByText(/đọc được: “09l2 34”/)).toBeInTheDocument();
  });

  it("Điền vào form: chỉ điền trường hợp lệ, đánh dấu AI, bỏ trường cần nhập tay", async () => {
    streamWith({ type: "done", result: RESULT });
    const { container, user } = setup();
    uploadFile(container);
    await user.click(await screen.findByRole("button", { name: "Điền vào form" }));
    expect(screen.getByLabelText(/Mã số thuế/)).toHaveValue("0101234567");
    expect(screen.getByLabelText(/Tên doanh nghiệp/)).toHaveValue("Công ty TNHH Sao Mai");
    expect(screen.getByLabelText(/SĐT người hướng dẫn/)).toHaveValue("");
    expect(screen.getByLabelText(/Mã số thuế/).closest(".field")).toHaveClass("is-ai");
    expect(screen.getByLabelText(/SĐT người hướng dẫn/).closest(".field")).not.toHaveClass("is-ai");
  });

  it("người dùng sửa ô do AI điền thì mất dấu AI", async () => {
    streamWith({ type: "done", result: RESULT });
    const { container, user } = setup();
    uploadFile(container);
    await user.click(await screen.findByRole("button", { name: "Điền vào form" }));
    const tax = screen.getByLabelText(/Mã số thuế/);
    await user.type(tax, "9");
    expect(tax.closest(".field")).not.toHaveClass("is-ai");
  });

  it("cảnh báo khi văn bản đến từ OCR (có thể sai chữ số)", async () => {
    streamWith({ type: "done", result: { ...RESULT, ocr: true } });
    const { container } = setup();
    uploadFile(container);
    expect(await screen.findByText(/có thể sai chữ số/)).toBeInTheDocument();
  });

  it("LLM lỗi: báo rõ chỉ có kết quả theo luật", async () => {
    streamWith({ type: "done", result: { ...RESULT, llm: { error: "timeout" } } });
    const { container } = setup();
    uploadFile(container);
    expect(await screen.findByRole("alert")).toHaveTextContent(/chỉ từ bộ trích xuất theo luật/);
  });

  it("backend báo lỗi qua SSE → hiện lỗi, không có bảng gợi ý", async () => {
    streamWith({ type: "error", detail: "File không đọc được" });
    const { container } = setup();
    uploadFile(container);
    expect(await screen.findByText("File không đọc được")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("kết nối ngắt trước khi xong → báo thử lại", async () => {
    streamWith({ type: "stage", stage: "read", label: "Đọc nội dung" });
    const { container } = setup();
    uploadFile(container);
    expect(await screen.findByText(/Kết nối bị ngắt/)).toBeInTheDocument();
  });

  it("lỗi mạng → hiện thông báo lỗi", async () => {
    streamIntake.mockImplementation(async () => { throw new Error("Mất mạng"); });
    const { container } = setup();
    uploadFile(container);
    expect(await screen.findByText("Mất mạng")).toBeInTheDocument();
  });
});

describe("RegistrationForm — lưu, kiểm tra, nộp", () => {
  it("lưu nháp: PATCH kèm version, ô trống thành null, danh sách trường AI", async () => {
    api.mockResolvedValue({ version: 4 });
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));
    await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    const [method, path, body] = api.mock.calls[0];
    expect([method, path]).toEqual(["PATCH", "/internships/5"]);
    expect(body).toMatchObject({ version: 3, company_name: "Công ty A", mode: "part_time", company_tax_code: null, ai_fields: [] });
  });

  it("kiểm tra theo quy chế: lưu rồi gọi validate; hiện điều không đạt", async () => {
    api.mockImplementation(async (method, path) =>
      path.endsWith("/validate") ? { results: [{ passed: false, message: "Thời gian thực tập chưa đủ 8 tuần" }] } : { version: 4 });
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    expect(await screen.findByText(/chưa đủ 8 tuần/)).toBeInTheDocument();
    expect(api.mock.calls.map((c) => c[1])).toEqual(["/internships/5", "/internships/5/validate"]);
  });

  it("mọi kiểm tra đạt → thông báo đạt", async () => {
    api.mockImplementation(async (method, path) => (path.endsWith("/validate") ? { results: [{ passed: true }] } : { version: 4 }));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Kiểm tra theo quy chế" }));
    expect(await screen.findByText("Hồ sơ đạt mọi kiểm tra của quy chế")).toBeInTheDocument();
  });

  it("nộp thành công: lưu → submit → reload", async () => {
    api.mockResolvedValue({ version: 4 });
    const { user, reload } = setup();
    await user.click(screen.getByRole("button", { name: "Xác nhận & nộp hồ sơ" }));
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(api.mock.calls.map((c) => `${c[0]} ${c[1]}`)).toEqual(["PATCH /internships/5", "POST /internships/5/submit"]);
  });

  it("nộp bị từ chối vì vi phạm quy chế: hiện lỗi, không reload", async () => {
    api.mockImplementation(async (method, path) => {
      if (path.endsWith("/submit")) {
        throw Object.assign(new Error("Hồ sơ chưa hợp lệ"), { detail: { errors: [{ passed: false, message: "Thiếu mã số thuế" }] } });
      }
      return { version: 4 };
    });
    const { user, reload } = setup();
    await user.click(screen.getByRole("button", { name: "Xác nhận & nộp hồ sơ" }));
    expect(await screen.findByText(/Thiếu mã số thuế/)).toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled();
  });
});
