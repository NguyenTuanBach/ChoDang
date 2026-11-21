import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import DecisionBox from "./DecisionBox";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));

const setup = (props) => {
  const onDone = vi.fn();
  render(
    <ToastProvider>
      <DecisionBox onDone={onDone} {...props} />
    </ToastProvider>,
  );
  return { onDone, user: userEvent.setup() };
};

beforeEach(() => {
  api.mockReset(); // không return: vitest coi hàm trả về từ beforeEach là teardown và sẽ gọi nó
});

describe("DecisionBox", () => {
  it("hồ sơ/đề cương có 3 lựa chọn: duyệt, yêu cầu sửa, từ chối", () => {
    setup({ kind: "outline", id: 7, version: 2 });
    for (const name of ["Duyệt", "Yêu cầu chỉnh sửa", "Từ chối"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("gia hạn chỉ có chấp nhận hoặc từ chối", () => {
    setup({ kind: "extension", id: 3 });
    expect(screen.getByRole("button", { name: "Chấp nhận gia hạn" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Từ chối" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yêu cầu chỉnh sửa" })).not.toBeInTheDocument();
  });

  it("ngoại lệ chỉ có chấp nhận hoặc từ chối và gửi tới /exceptions", async () => {
    api.mockResolvedValue({});
    const { user, onDone } = setup({ kind: "exception", id: 9 });
    expect(screen.queryByRole("button", { name: "Yêu cầu chỉnh sửa" })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/Lý do/), "Có xác nhận");
    await user.click(screen.getByRole("button", { name: "Chấp nhận ngoại lệ" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(api).toHaveBeenCalledWith("POST", "/exceptions/9/decision", { decision: "approved", reason: "Có xác nhận" });
  });

  it("không tự quyết định: chưa bấm nút thì không gọi API", () => {
    setup({ kind: "internship", id: 1, version: 1 });
    expect(api).not.toHaveBeenCalled();
  });

  it("gửi quyết định kèm nhận xét và version (khóa lạc quan) tới đúng endpoint", async () => {
    api.mockResolvedValue({});
    const { user, onDone } = setup({ kind: "outline", id: 7, version: 2 });
    await user.type(screen.getByRole("textbox"), "Thiếu mục tiêu kiểm thử");
    await user.click(screen.getByRole("button", { name: "Yêu cầu chỉnh sửa" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(api).toHaveBeenCalledWith("POST", "/outlines/7/decision", {
      decision: "revision_requested",
      reason: "Thiếu mục tiêu kiểm thử",
      version: 2,
    });
  });

  it("gia hạn không gửi version", async () => {
    api.mockResolvedValue({});
    const { user, onDone } = setup({ kind: "extension", id: 3 });
    await user.click(screen.getByRole("button", { name: "Từ chối" }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(api).toHaveBeenCalledWith("POST", "/extensions/3/decision", { decision: "rejected", reason: "" });
  });

  it("API lỗi (vd. thiếu nhận xét, version cũ) → hiện lỗi và không báo xong", async () => {
    api.mockRejectedValue(new Error("Cần nhập nhận xét"));
    const { user, onDone } = setup({ kind: "internship", id: 1, version: 1 });
    await user.click(screen.getByRole("button", { name: "Từ chối" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Cần nhập nhận xét");
    expect(onDone).not.toHaveBeenCalled();
  });
});
