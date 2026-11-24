import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { setPendingAutofill } from "@/lib/autofill";
import { toast } from "sonner";
import OutlinePage from "./OutlinePage";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const DETAIL = {
  internship: { id: 1, status: "confirmed", cohort: "2026-K1" },
  outlines: [],
  milestones: [],
  journals: [],
  evidence: [],
  documents: [],
  outcomes: [],
};

function stubFetch(postResult: unknown) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      calls.push({ url, method, body: init?.body as string | undefined });
      if (url === "/api/student/internship") return new Response(JSON.stringify(DETAIL));
      if (url === "/api/student/outlines" && method === "POST") return new Response(JSON.stringify(postResult));
      return new Response("{}", { status: 404 });
    }),
  );
  return calls;
}

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => vi.unstubAllGlobals());

async function fillAll() {
  await userEvent.type(await screen.findByLabelText(/Mục tiêu/), "Học quy trình phát triển web tại doanh nghiệp");
  await userEvent.type(screen.getByLabelText(/Nhiệm vụ/), "Làm API và viết kiểm thử");
  await userEvent.type(screen.getByLabelText(/Kế hoạch/), "Tuần 1-12 theo từng giai đoạn");
  await userEvent.type(screen.getByLabelText(/Kết quả dự kiến/), "Hoàn thành ba chức năng");
}

describe("OutlinePage", () => {
  it("điền đủ bốn ô thì nút Nộp bấm được và gửi văn bản ghép có đủ tiêu đề", async () => {
    const calls = stubFetch({ saved: true, id: 7, issues: [], summary: "Tốt", ai: true, outcome_codes: [] });
    render(<OutlinePage />);
    const submit = await screen.findByRole("button", { name: "Nộp đề cương" });
    expect((submit as HTMLButtonElement).disabled).toBe(true); // chưa nhập gì

    await fillAll();
    expect((submit as HTMLButtonElement).disabled).toBe(false);
    await userEvent.click(submit);

    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === "/api/student/outlines")).toBe(true));
    const body = JSON.parse(calls.find((c) => c.method === "POST")!.body!);
    for (const heading of ["Mục tiêu:", "Nhiệm vụ:", "Kế hoạch:", "Kết quả dự kiến:"]) expect(body.content).toContain(heading);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Đã nộp đề cương")));
  });

  it("backend báo thiếu phần thì hiện lỗi ngay dưới đúng ô", async () => {
    stubFetch({
      saved: false,
      id: null,
      issues: [{ section: "Nhiệm vụ", level: "error", message: "Chưa thấy phần “Nhiệm vụ” trong đề cương." }],
      summary: "",
      ai: true,
      outcome_codes: [],
    });
    render(<OutlinePage />);
    await fillAll();
    await userEvent.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    expect(await screen.findByText(/Chưa thấy phần “Nhiệm vụ”/)).toBeTruthy();
    expect(await screen.findByText("Chưa nộp được đề cương")).toBeTruthy();
  });
});

describe("OutlinePage tự điền từ ngăn Trợ lý", () => {
  const FIELDS = {
    objective: { value: "Mục tiêu từ tệp", confidence: 0.9, source: "" },
    tasks: { value: "Nhiệm vụ từ tệp", confidence: 0.9, source: "" },
    plan: { value: "Kế hoạch từ tệp", confidence: 0.9, source: "" },
    results: { value: "Kết quả từ tệp", confidence: 0.9, source: "" },
  };

  it("trang đang mở khi ngăn Trợ lý đặt gợi ý: bốn ô được điền", async () => {
    stubFetch({});
    render(<OutlinePage />);
    await screen.findByLabelText(/Mục tiêu/);
    act(() => setPendingAutofill({ kind: "outline", documentId: null, evidenceId: null, fields: FIELDS, warnings: [] }));
    await waitFor(() => expect((screen.getByLabelText(/Mục tiêu/) as HTMLTextAreaElement).value).toBe("Mục tiêu từ tệp"));
    expect((screen.getByLabelText(/Nhiệm vụ/) as HTMLTextAreaElement).value).toBe("Nhiệm vụ từ tệp");
    expect((screen.getByLabelText(/Kế hoạch/) as HTMLTextAreaElement).value).toBe("Kế hoạch từ tệp");
    expect((screen.getByLabelText(/Kết quả dự kiến/) as HTMLTextAreaElement).value).toBe("Kết quả từ tệp");
  });

  it("gợi ý đặt trước rồi mới mở trang: bốn ô được điền ngay", async () => {
    stubFetch({});
    setPendingAutofill({ kind: "outline", documentId: null, evidenceId: null, fields: FIELDS, warnings: [] });
    render(<OutlinePage />);
    expect(((await screen.findByLabelText(/Mục tiêu/)) as HTMLTextAreaElement).value).toBe("Mục tiêu từ tệp");
    expect((screen.getByLabelText(/Kết quả dự kiến/) as HTMLTextAreaElement).value).toBe("Kết quả từ tệp");
  });
});

describe("OutlinePage danh sách phiên bản", () => {
  it("mỗi phiên bản có thẻ phiên bản và thẻ nhận xét riêng, nằm trong thẻ các phiên bản đã nộp", async () => {
    const detail = {
      ...DETAIL,
      internship: { ...DETAIL.internship, status: "in_progress" },
      outlines: [
        {
          id: 1,
          version: 1,
          content: "Mục tiêu: học web",
          outcome_codes: ["LO1"],
          status: "approved",
          feedback: "Đề cương tốt.",
          submitted_at: "2026-11-24T08:00:00Z",
          ai_review: { summary: "Rõ ràng.", issues: [{ section: "Kế hoạch", level: "warning", message: "Thêm mốc thời gian." }], ai: true },
        },
      ],
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(detail))));
    render(<OutlinePage />);
    const comments = await screen.findByText("Nhận xét · Phiên bản 1");
    const commentsCard = comments.closest("section")!;
    expect(commentsCard.textContent).toContain("Đề cương tốt."); // nhận xét của giảng viên
    expect(commentsCard.textContent).toContain("Rõ ràng."); // nhận xét của AI
    expect(commentsCard.textContent).toContain("Thêm mốc thời gian.");
    expect(commentsCard.textContent).not.toContain("Mục tiêu: học web"); // nội dung phiên bản ở thẻ riêng
    const versionsCard = screen.getByText("Các phiên bản đã nộp").closest("section")!;
    expect(versionsCard.contains(commentsCard)).toBe(true);
    expect(versionsCard.textContent).toContain("Mục tiêu: học web");
  });
});

describe("OutlinePage sau khi nộp", () => {
  it("nộp thành công thì bốn ô được xóa sạch", async () => {
    stubFetch({ saved: true, id: 7, issues: [], summary: "", ai: true, outcome_codes: [] });
    render(<OutlinePage />);
    await fillAll();
    await userEvent.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("Đã nộp đề cương")));
    for (const label of [/Mục tiêu/, /Nhiệm vụ/, /Kế hoạch/, /Kết quả dự kiến/]) {
      expect((screen.getByLabelText(label) as HTMLTextAreaElement).value).toBe("");
    }
  });

  it("chưa nộp được (thiếu phần) thì giữ nguyên chữ đã nhập để sửa", async () => {
    stubFetch({
      saved: false,
      id: null,
      issues: [{ section: "Nhiệm vụ", level: "error", message: "Chưa thấy phần “Nhiệm vụ” trong đề cương." }],
      summary: "",
      ai: true,
      outcome_codes: [],
    });
    render(<OutlinePage />);
    await fillAll();
    await userEvent.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    await screen.findByText("Chưa nộp được đề cương");
    expect((screen.getByLabelText(/Mục tiêu/) as HTMLTextAreaElement).value).toContain("Học quy trình");
  });
});

describe("OutlinePage lưu tệp đính kèm", () => {
  it("tải tệp đề cương rồi nộp thành công thì tệp được lưu kèm phiên bản vừa nộp", async () => {
    const calls: { url: string; method: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        calls.push({ url, method });
        if (url === "/api/student/internship") return new Response(JSON.stringify(DETAIL));
        if (url === "/api/student/outlines/extract") {
          return new Response(JSON.stringify({ fields: { objective: { value: "Học quy trình phát triển web tại doanh nghiệp" }, tasks: { value: "Làm API và viết kiểm thử" }, plan: { value: "Tuần 1-12 theo từng giai đoạn" }, results: { value: "Hoàn thành ba chức năng" } }, notes: "" }));
        }
        if (url === "/api/student/outlines" && method === "POST") return new Response(JSON.stringify({ saved: true, id: 7, issues: [], summary: "", ai: true, outcome_codes: [] }));
        if (url === "/api/student/outlines/7/file") return new Response(JSON.stringify({ id: 7, file_name: "de-cuong.pdf", file_size: 3 }), { status: 201 });
        return new Response("{}", { status: 404 });
      }),
    );
    const { container } = render(<OutlinePage />);
    await screen.findByLabelText(/Mục tiêu/);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File(["%PDF-1.4"], "de-cuong.pdf", { type: "application/pdf" }));
    await userEvent.click(await screen.findByRole("button", { name: "Tải lên" }));
    expect(await screen.findByText("de-cuong.pdf")).toBeTruthy(); // chip tệp sẽ lưu kèm
    await userEvent.click(screen.getByRole("button", { name: "Nộp đề cương" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/student/outlines/7/file" && c.method === "POST")).toBe(true));
  });

  it("chưa chọn tệp thì không có chip tệp đính kèm", async () => {
    stubFetch({ saved: true, id: 7, issues: [], summary: "", ai: true, outcome_codes: [] });
    const { container } = render(<OutlinePage />);
    await screen.findByLabelText(/Mục tiêu/);
    // Không có tệp đính kèm thì không có chip nào để bỏ.
    expect(container.querySelector('[aria-label="Bỏ tệp đính kèm"]')).toBeNull();
  });
});
