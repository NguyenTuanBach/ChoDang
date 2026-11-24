import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import InternshipForm from "./InternshipForm";

function detail(status: string) {
  return {
    internship: {
      id: 1,
      status,
      version: 1,
      cohort: "2026-K1",
      company_name: "Công ty Mẫu",
      company_tax_code: "0100000000",
      company_address: "12 Đường Mẫu",
      position: "Thực tập sinh",
      department: "Phát triển",
      mentor_name: "Anh Mẫu",
      mentor_title: "Trưởng nhóm",
      mentor_email: "mentor@congty-mau.example",
      mentor_phone: "0901234567",
      job_description: "Viết mã và kiểm thử",
      start_date: "2026-12-01",
      end_date: "2027-02-28",
      mode: "onsite",
      field_confirmations: {},
      lecturer_name: "Cô Lan",
      decision_reason: "",
    },
    documents: [],
    outlines: [],
    milestones: [],
    journals: [],
    evidence: [],
    outcomes: [],
    checks: [],
  };
}

function stubFetch(status: string) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      calls.push({ url, method, body: init?.body as string | undefined });
      if (url === "/api/student/internship" && method === "GET") return new Response(JSON.stringify(detail(status)));
      if (url === "/api/student/internship" && method === "PUT") return new Response(JSON.stringify({ internship: detail(status).internship, checks: [] }));
      if (url === "/api/student/internship/personal") return new Response(JSON.stringify({ internship: detail(status).internship }));
      return new Response("{}", { status: 404 });
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

const disabled = (label: RegExp) => (screen.getByLabelText(label) as HTMLInputElement).disabled;

describe("InternshipForm sau khi nộp", () => {
  it("khóa thông tin công ty và thời gian, mở vị trí / mô tả công việc / hình thức", async () => {
    stubFetch("in_progress");
    render(<InternshipForm />);
    await screen.findByLabelText(/Vị trí thực tập/);
    for (const locked of [/Tên doanh nghiệp/, /Mã số thuế/, /Địa chỉ doanh nghiệp/, /Người hướng dẫn tại doanh nghiệp/, /Email người hướng dẫn/, /Ngày bắt đầu/, /Ngày kết thúc/]) {
      expect(disabled(locked)).toBe(true);
    }
    for (const open of [/Vị trí thực tập/, /Mô tả công việc/, /Hình thức thực tập/]) expect(disabled(open)).toBe(false);
    expect(screen.queryByRole("button", { name: "Lưu bản nháp" })).toBeNull();
  });

  it("bấm Lưu thông tin cá nhân chỉ gửi vị trí, mô tả công việc và hình thức", async () => {
    const calls = stubFetch("submitted");
    render(<InternshipForm />);
    const position = await screen.findByLabelText(/Vị trí thực tập/);
    await userEvent.clear(position);
    await userEvent.type(position, "Backend intern");
    await userEvent.click(screen.getByRole("button", { name: "Lưu thông tin cá nhân" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/student/internship/personal")).toBe(true));
    const body = JSON.parse(calls.find((c) => c.url === "/api/student/internship/personal")!.body!);
    expect(Object.keys(body).sort()).toEqual(["job_description", "mode", "position"]);
    expect(body.position).toBe("Backend intern");
  });

  it("hồ sơ nháp vẫn sửa được tất cả và không có nút lưu cá nhân", async () => {
    stubFetch("draft");
    render(<InternshipForm />);
    await screen.findByLabelText(/Vị trí thực tập/);
    expect(disabled(/Tên doanh nghiệp/)).toBe(false);
    expect(screen.queryByRole("button", { name: "Lưu thông tin cá nhân" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Lưu bản nháp" }).length).toBeGreaterThan(0);
  });

  it("hồ sơ đã kết thúc thì khóa tất cả", async () => {
    stubFetch("completed");
    render(<InternshipForm />);
    await screen.findByLabelText(/Vị trí thực tập/);
    expect(disabled(/Vị trí thực tập/)).toBe(true);
    expect(screen.queryByRole("button", { name: "Lưu thông tin cá nhân" })).toBeNull();
  });
});

describe("InternshipForm khi chưa có hồ sơ", () => {
  it("không sập dù BE không trả danh sách giấy; hiện nút tải giấy tiếp nhận", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ internship: null, outcomes: [], checks: [] }))));
    render(<InternshipForm />);
    expect((await screen.findAllByRole("button", { name: "Tải giấy tiếp nhận" })).length).toBe(2); // một ở thẻ Thông tin thực tập, một ở thẻ giấy tiếp nhận
    expect(screen.getAllByText(/Chưa tải giấy tiếp nhận/).length).toBe(2); // khung trống ở cả hai thẻ
  });
});

describe("InternshipForm: kiểm tra trước khi nộp với thay đổi chưa lưu", () => {
  it("chưa sửa gì thì không có cảnh báo; sửa ô thì báo chưa lưu, khóa nút Nộp, và lưu được ngay trong thẻ", async () => {
    const calls = stubFetch("draft");
    render(<InternshipForm />);
    const company = await screen.findByLabelText(/Tên doanh nghiệp/);
    expect(screen.queryByText("Có thay đổi chưa lưu")).toBeNull();

    await userEvent.type(company, " mới");
    expect(await screen.findByText("Có thay đổi chưa lưu")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Nộp hồ sơ cho giảng viên" }) as HTMLButtonElement).disabled).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: "Lưu và kiểm tra lại" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.url === "/api/student/internship")).toBe(true));
  });
});

describe("InternshipForm: giấy tiếp nhận và kết quả kiểm tra gọn", () => {
  function stubDraft(extra: Record<string, unknown>) {
    const base = detail("draft");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...base, ...extra }))));
  }

  it("chỉ hiện MỘT giấy tiếp nhận (mới nhất) và không có nút AI gợi ý hay tải giấy khác", async () => {
    stubDraft({
      documents: [
        { id: 1, filename: "giay-cu.png", uploaded_at: "2026-11-20T08:00:00Z" },
        { id: 2, filename: "giay-moi.png", uploaded_at: "2026-11-24T08:00:00Z" },
      ],
    });
    render(<InternshipForm />);
    expect((await screen.findAllByText("giay-moi.png")).length).toBe(2); // cùng một tệp ở hai thẻ
    expect(screen.queryByText("giay-cu.png")).toBeNull();
    expect(screen.queryByRole("button", { name: /Tải giấy/ })).toBeNull(); // đã có giấy: chỉ còn đường link
    expect(screen.queryByRole("button", { name: "AI gợi ý các trường" })).toBeNull();
  });

  it("kiểm tra chỉ liệt kê mục chưa đạt, không có dòng Đạt", async () => {
    stubDraft({
      checks: [
        { code: "required:company_name", label: "Tên doanh nghiệp đã điền", ok: true, level: "error", detail: "", citation: null },
        { code: "required:position", label: "Vị trí thực tập đã điền", ok: false, level: "error", detail: "Còn thiếu", citation: null },
        { code: "receipt_letter", label: "Đã tải giấy tiếp nhận", ok: false, level: "warning", detail: "Nên tải", citation: null },
      ],
    });
    render(<InternshipForm />);
    expect(await screen.findByText(/Vị trí thực tập đã điền — Còn thiếu/)).toBeTruthy();
    expect(screen.getByText(/Đã tải giấy tiếp nhận — Nên tải/)).toBeTruthy();
    expect(screen.queryByText(/Tên doanh nghiệp đã điền/)).toBeNull(); // mục đạt không hiện
    expect(screen.queryByText("Đạt")).toBeNull();
    expect(screen.getByText("Lỗi")).toBeTruthy();
    expect(screen.getByText("Lưu ý")).toBeTruthy();
  });

  it("mọi mục đạt thì chỉ hiện một dòng xác nhận, không liệt kê từng mục", async () => {
    stubDraft({ checks: [{ code: "required:company_name", label: "Tên doanh nghiệp đã điền", ok: true, level: "error", detail: "", citation: null }] });
    render(<InternshipForm />);
    expect(await screen.findByText(/Không có mục nào cần sửa/)).toBeTruthy();
    expect(screen.queryByText(/Tên doanh nghiệp đã điền/)).toBeNull();
  });
});

describe("InternshipForm: form riêng của giấy tiếp nhận", () => {
  it("bốn ô của tờ giấy nằm trong thẻ giấy tiếp nhận, không nằm trong thẻ Thông tin thực tập", async () => {
    stubFetch("draft");
    render(<InternshipForm />);
    const letterCard = (await screen.findByText("Giấy tiếp nhận của doanh nghiệp")).closest("section")!;
    const infoCard = screen.getByText("Thông tin thực tập").closest("section")!;
    for (const label of [/Số hiệu giấy/, /Ngày ký giấy/, /Người ký giấy/, /Chức vụ người ký/]) {
      const input = screen.getByLabelText(label);
      expect(letterCard.contains(input)).toBe(true);
      expect(infoCard.contains(input)).toBe(false);
    }
    expect(infoCard.contains(screen.getByLabelText(/Tên doanh nghiệp/))).toBe(true);
  });
});

describe("InternshipForm: khung tải giấy tiếp nhận", () => {
  it("bấm hoặc kéo thả tệp vào khung thì mở popup xem lại, không còn nút tải đứng riêng", async () => {
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() }));
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ internship: null, outcomes: [], checks: [] }))));
    render(<InternshipForm />);
    const zones = await screen.findAllByRole("button", { name: "Tải giấy tiếp nhận" });
    expect(zones.length).toBe(2);
    expect(zones[0].textContent).toContain("kéo thả"); // khung chứa lời hướng dẫn, không phải nút nhỏ riêng
    const file = new File(["%PDF-1.4"], "giay.pdf", { type: "application/pdf" });
    const drop = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(drop, "dataTransfer", { value: { files: [file] } });
    zones[0].dispatchEvent(drop);
    expect((await screen.findAllByText("Xem lại giấy tiếp nhận")).length).toBeGreaterThan(0);
  });
});
