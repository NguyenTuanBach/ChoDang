import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import RequestsPage from "./RequestsPage";

const TYPES = [{ code: "sick", name: "Nghỉ ốm", affects_credit: false, active: true }];

function stub(internship: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/student/requests") return new Response("[]");
      if (url === "/api/exception-types") return new Response(JSON.stringify(TYPES));
      if (url === "/api/student/internship") return new Response(JSON.stringify({ internship, outcomes: [], checks: [] }));
      return new Response("{}", { status: 404 });
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

const applyButtons = () => screen.getAllByRole("button", { name: "Áp dụng" }) as HTMLButtonElement[];

describe("RequestsPage", () => {
  it("chưa đăng ký hồ sơ: khóa mọi nút Áp dụng và báo lý do", async () => {
    stub(null);
    render(<RequestsPage />);
    expect(await screen.findByText("Chưa gửi được đơn")).toBeTruthy();
    expect(screen.getByText(/chưa đăng ký hồ sơ thực tập/)).toBeTruthy();
    expect(applyButtons().length).toBeGreaterThan(0);
    for (const b of applyButtons()) expect(b.disabled).toBe(true);
  });

  it("hồ sơ mới là bản nháp (chưa được xác nhận): vẫn khóa", async () => {
    stub({ id: 1, status: "draft" });
    render(<RequestsPage />);
    expect(await screen.findByText("Chưa gửi được đơn")).toBeTruthy();
    for (const b of applyButtons()) expect(b.disabled).toBe(true);
  });

  it("đang thực tập: bật nút Áp dụng và không hiện thông báo chặn", async () => {
    stub({ id: 1, status: "in_progress" });
    render(<RequestsPage />);
    await screen.findByText("Nghỉ ốm");
    await vi.waitFor(() => expect(applyButtons().every((b) => !b.disabled)).toBe(true));
    expect(screen.queryByText("Chưa gửi được đơn")).toBeNull();
  });
});
