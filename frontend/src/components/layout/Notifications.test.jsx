import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import Notifications from "./Notifications";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

const item = (over = {}) => ({ id: 1, title: "Mốc quá hạn", body: "Báo cáo giữa kỳ", link: "#/internship/3", read: false, created_at: "2027-02-05T03:00:00", ...over });

function Host({ initialOpen = false }) {
  const [open, setOpen] = useState(initialOpen);
  return <MemoryRouter><Notifications open={open} setOpen={setOpen} /></MemoryRouter>;
}

/** GET /notifications trả danh sách; POST read-all đánh dấu đã đọc như máy chủ thật. */
const setup = (list, { open = false } = {}) => {
  let current = list;
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/notifications") return current;
    if (method === "POST" && path === "/notifications/read-all") { current = current.map((n) => ({ ...n, read: true })); return {}; }
    return {};
  });
  render(<Host initialOpen={open} />);
  return userEvent.setup();
};

beforeEach(() => {
  api.mockReset();
});

describe("Notifications — chuông thông báo", () => {
  it("hiện số thông báo chưa đọc trên chuông", async () => {
    setup([item({ id: 1 }), item({ id: 2 }), item({ id: 3, read: true })]);
    expect(await screen.findByText("2")).toBeInTheDocument();
  });

  it("không có thông báo chưa đọc thì không hiện số", async () => {
    setup([item({ read: true })]);
    await waitFor(() => expect(api).toHaveBeenCalledWith("GET", "/notifications"));
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });

  it("panel đóng sẵn; bấm chuông mở panel và đánh dấu đã đọc", async () => {
    const user = setup([item()]);
    const bell = await screen.findByRole("button", { name: "Thông báo" });
    expect(bell).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog", { name: "Thông báo" })).not.toBeInTheDocument();

    await user.click(bell);
    expect(await screen.findByRole("dialog", { name: "Thông báo" })).toBeInTheDocument();
    expect(bell).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(api).toHaveBeenCalledWith("POST", "/notifications/read-all"));
    await waitFor(() => expect(screen.queryByText("1")).not.toBeInTheDocument());
  });

  it("mở panel khi không có gì chưa đọc thì không gọi read-all", async () => {
    const user = setup([item({ read: true })]);
    await user.click(await screen.findByRole("button", { name: "Thông báo" }));
    await screen.findByRole("dialog", { name: "Thông báo" });
    expect(api).not.toHaveBeenCalledWith("POST", "/notifications/read-all");
  });

  it("bấm chuông lần nữa thì đóng panel", async () => {
    const user = setup([item()]);
    const bell = await screen.findByRole("button", { name: "Thông báo" });
    await user.click(bell);
    await screen.findByRole("dialog", { name: "Thông báo" });
    await user.click(bell);
    expect(screen.queryByRole("dialog", { name: "Thông báo" })).not.toBeInTheDocument();
  });
});

describe("Notifications — nội dung panel", () => {
  it("mỗi thông báo có tiêu đề, nội dung và link bỏ dấu # của hash-router cũ", async () => {
    setup([item()], { open: true });
    const link = await screen.findByRole("link", { name: /Mốc quá hạn/ });
    expect(link).toHaveAttribute("href", "/internship/3");
    expect(link).toHaveTextContent("Báo cáo giữa kỳ");
  });

  it("thông báo không có link thì về trang chủ", async () => {
    setup([item({ link: null })], { open: true });
    expect(await screen.findByRole("link", { name: /Mốc quá hạn/ })).toHaveAttribute("href", "/");
  });

  it("danh sách rỗng → báo chưa có thông báo", async () => {
    setup([], { open: true });
    expect(await screen.findByText("Chưa có thông báo.")).toBeInTheDocument();
  });

  it("API lỗi không làm hỏng trang: chuông vẫn hiện, không có số", async () => {
    api.mockRejectedValue(new Error("mất mạng"));
    render(<Host />);
    expect(await screen.findByRole("button", { name: "Thông báo" })).toBeInTheDocument();
    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });
});
