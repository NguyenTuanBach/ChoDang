import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IntakeProgress from "./IntakeProgress";

const progress = (over = {}) => ({ stage: "upload", label: "Đang tải file lên…", fileName: "giay.pdf", startedAt: Date.now(), ocr: false, ...over });
const steps = () => screen.getAllByRole("listitem");

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("IntakeProgress — các bước", () => {
  it("file thường: 3 bước, không có bước OCR", () => {
    render(<IntakeProgress progress={progress()} />);
    expect(steps().map((s) => s.textContent)).toEqual(["Nhận file", "Đọc nội dung", "Trích xuất các trường"].map((t, i) => (i === 0 ? t : `${i + 1}${t}`)));
    expect(screen.queryByText(/OCR/)).not.toBeInTheDocument();
  });

  it("bước hiện tại có aria-current, bước trước đánh dấu xong, bước sau chưa làm", () => {
    render(<IntakeProgress progress={progress({ stage: "read", label: "Đang đọc" })} />);
    const [first, second, third] = steps();
    expect(first).toHaveClass("is-done");
    expect(second).toHaveClass("is-active");
    expect(second).toHaveAttribute("aria-current", "step");
    expect(third).toHaveClass("is-todo");
    expect(third).not.toHaveAttribute("aria-current");
  });

  it("stage lạ → coi như bước đầu", () => {
    render(<IntakeProgress progress={progress({ stage: "khong-biet" })} />);
    expect(steps()[0]).toHaveClass("is-active");
  });

  it("hiện nhãn tiến trình, tên file và vùng trạng thái cho trình đọc màn hình", () => {
    render(<IntakeProgress progress={progress({ label: "Đang đọc nội dung" })} />);
    expect(screen.getByText("Đang đọc nội dung")).toBeInTheDocument();
    expect(screen.getByText(/giay\.pdf · 0s/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });
});

describe("IntakeProgress — OCR", () => {
  it("bản scan: thêm bước OCR giữa 'Đọc nội dung' và 'Trích xuất', kèm gợi ý thời gian", () => {
    render(<IntakeProgress progress={progress({ stage: "ocr", ocr: true })} />);
    expect(steps()).toHaveLength(4);
    expect(steps()[2]).toHaveTextContent("Nhận dạng chữ trên ảnh (OCR)");
    expect(steps()[2]).toHaveClass("is-active");
    expect(screen.getByText(/mất vài chục giây/)).toBeInTheDocument();
  });

  it("thanh tiến độ theo trang: đang ở trang 2/3 → 50% (tính nửa trang đang xử lý)", () => {
    render(<IntakeProgress progress={progress({ stage: "ocr", ocr: true, page: 2, pages: 3 })} />);
    const bar = screen.getByRole("progressbar", { name: "Tiến độ nhận dạng chữ" });
    expect(bar).toHaveAttribute("aria-valuenow", "50");
    expect(steps()[2]).toHaveTextContent("— trang 2/3");
  });

  it("trang đầu chưa xong vẫn có tiến độ > 0", () => {
    render(<IntakeProgress progress={progress({ stage: "ocr", ocr: true, page: 1, pages: 4 })} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "13");
  });

  it("chưa biết số trang hoặc không ở bước OCR → không có thanh tiến độ", () => {
    const { rerender } = render(<IntakeProgress progress={progress({ stage: "ocr", ocr: true, pages: 0 })} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    rerender(<IntakeProgress progress={progress({ stage: "extract", ocr: true, page: 2, pages: 3 })} />);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(steps()[3]).toHaveClass("is-active"); // đã qua OCR, đang trích xuất
  });
});

describe("IntakeProgress — đồng hồ", () => {
  it("đếm giây đã trôi qua", () => {
    render(<IntakeProgress progress={progress()} />);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.getByText(/giay\.pdf · 3s/)).toBeInTheDocument();
  });

  it("đang đọc file quá 4 giây → nhắc chờ; chưa tới 4 giây thì không", () => {
    render(<IntakeProgress progress={progress({ stage: "read" })} />);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.queryByText(/Đang đọc file, vui lòng chờ/)).not.toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(1500); });
    expect(screen.getByText(/Đang đọc file, vui lòng chờ/)).toBeInTheDocument();
  });

  it("bản scan thì không hiện nhắc 'đang đọc file' (đã có gợi ý OCR riêng)", () => {
    render(<IntakeProgress progress={progress({ stage: "read", ocr: true })} />);
    act(() => { vi.advanceTimersByTime(6000); });
    expect(screen.queryByText(/Đang đọc file, vui lòng chờ/)).not.toBeInTheDocument();
  });

  it("gỡ component thì dừng đồng hồ (không còn timer)", () => {
    const { unmount } = render(<IntakeProgress progress={progress()} />);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
