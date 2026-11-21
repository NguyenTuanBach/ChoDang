import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../context/ToastContext";
import { api } from "../../lib/api";
import StudentHome from "./StudentHome";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    me: { full_name: "Nguyễn Văn An" },
    config: { cohort: { name: "Học kỳ 1/2027", start_window: "2027-01-01", end_window: "2027-06-30", min_weeks: 8 } },
  }),
}));
// Các khối con có test riêng (hoặc thuộc nhóm khác) → thay bằng bản giả để kiểm tra đúng việc StudentHome quyết định hiện gì
vi.mock("./RegistrationForm", () => ({ default: (p) => <div data-testid="reg" data-editable={String(p.editable)} /> }));
vi.mock("./Outline", () => ({ default: () => <div data-testid="outline" /> }));
vi.mock("./ExtensionList", () => ({ default: () => <div data-testid="extensions" /> }));
vi.mock("./ExceptionPanel", () => ({ default: () => <div data-testid="exceptions" /> }));
vi.mock("./Timeline", async (orig) => ({ ...(await orig()), default: () => <div data-testid="timeline" /> }));

const milestone = (over = {}) => ({ id: 1, name: "Báo cáo giữa kỳ", status: "pending", due_date: "2027-02-01", days_left: 5, ...over });
const internship = (over = {}) => ({ id: 3, version: 1, status: "draft", lecturer: { full_name: "TS. Trần" }, milestones: [], decision_reason: null, ...over });

const setup = ({ list = [{ id: 3 }], i = internship(), flags = [], extensions = [] } = {}) => {
  api.mockImplementation(async (method, path) => {
    if (method === "GET" && path === "/internships") return list;
    if (method === "GET" && path === "/internships/3") return i;
    if (path === "/risk-flags") return flags;
    if (path === "/internships/3/extensions") return extensions;
    if (path === "/internships/3/exceptions") return [];
    return {};
  });
  render(<ToastProvider><StudentHome /></ToastProvider>);
  return userEvent.setup();
};

beforeEach(() => {
  api.mockReset(); // không return: vitest coi hàm trả về từ beforeEach là teardown và gọi nó
});

describe("StudentHome — chưa có hồ sơ", () => {
  it("chào bằng tên cuối, hiện đợt và khung thời gian, mời tạo hồ sơ", async () => {
    setup({ list: [] });
    expect(await screen.findByRole("heading", { name: "Xin chào, An" })).toBeInTheDocument();
    expect(screen.getByText("Đợt thực tập: Học kỳ 1/2027")).toBeInTheDocument();
    expect(screen.getByText(/tối thiểu 8 tuần/)).toBeInTheDocument();
    expect(screen.queryByTestId("reg")).not.toBeInTheDocument();
  });

  it("tạo hồ sơ nháp: POST rồi tải lại danh sách", async () => {
    const user = setup({ list: [] });
    await user.click(await screen.findByRole("button", { name: "Tạo hồ sơ đăng ký" }));
    await waitFor(() => expect(api.mock.calls.filter((c) => c[0] === "GET" && c[1] === "/internships")).toHaveLength(2));
    expect(api).toHaveBeenCalledWith("POST", "/internships", {});
  });

  it("tạo hồ sơ lỗi → hiện lỗi, không tải lại", async () => {
    const user = setup({ list: [] });
    api.mockImplementation(async (method) => { if (method === "POST") throw new Error("Ngoài khung đăng ký"); return []; });
    await user.click(await screen.findByRole("button", { name: "Tạo hồ sơ đăng ký" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Ngoài khung đăng ký");
  });
});

describe("StudentHome — đã có hồ sơ", () => {
  it("tiêu đề có GV phụ trách; chưa phân công thì ghi rõ", async () => {
    setup();
    expect(await screen.findByText("Đợt Học kỳ 1/2027 · GV phụ trách: TS. Trần")).toBeInTheDocument();
  });

  it("chưa phân công giảng viên", async () => {
    setup({ i: internship({ lecturer: null }) });
    expect(await screen.findByText(/GV phụ trách: chưa phân công/)).toBeInTheDocument();
  });

  it("lấy hồ sơ đầu tiên trong danh sách và tải cảnh báo + gia hạn của hồ sơ đó", async () => {
    setup({ list: [{ id: 3 }, { id: 99 }] });
    await screen.findByTestId("reg");
    const paths = api.mock.calls.map((c) => c[1]);
    expect(paths).toEqual(expect.arrayContaining(["/internships/3", "/risk-flags", "/internships/3/extensions"]));
    expect(paths).not.toContain("/internships/99");
  });

  it.each([["draft", true], ["revision_requested", true], ["submitted", false], ["approved", false], ["in_progress", false], ["rejected", false]])(
    "trạng thái %s → form sửa được = %s", async (status, editable) => {
      setup({ i: internship({ status }) });
      expect((await screen.findByTestId("reg")).dataset.editable).toBe(String(editable));
    });

  it("lỗi tải hồ sơ → hiện lỗi", async () => {
    api.mockRejectedValue(new Error("Mất kết nối"));
    render(<ToastProvider><StudentHome /></ToastProvider>);
    expect(await screen.findByText("Mất kết nối")).toBeInTheDocument();
  });
});

describe("StudentHome — việc tiếp theo", () => {
  it("chưa có mốc → không có dòng việc tiếp theo, không có thẻ mốc", async () => {
    setup();
    await screen.findByTestId("reg");
    expect(screen.queryByText(/Việc tiếp theo/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("timeline")).not.toBeInTheDocument();
  });

  it("mốc còn hạn: ghi số ngày còn lại", async () => {
    setup({ i: internship({ status: "in_progress", milestones: [milestone({ status: "accepted", id: 0, name: "Đã xong" }), milestone()] }) });
    expect(await screen.findByText(/Việc tiếp theo: Báo cáo giữa kỳ/)).toBeInTheDocument();
    expect(screen.getByText(/còn 5 ngày/)).toBeInTheDocument();
    expect(screen.getByTestId("timeline")).toBeInTheDocument();
  });

  it("mốc quá hạn: ghi số ngày quá hạn", async () => {
    setup({ i: internship({ status: "in_progress", milestones: [milestone({ days_left: -3, status: "overdue" })] }) });
    expect(await screen.findByText(/quá hạn 3 ngày/)).toBeInTheDocument();
  });

  it("hết hạn đúng hôm nay (0 ngày) vẫn tính là còn hạn", async () => {
    setup({ i: internship({ status: "in_progress", milestones: [milestone({ days_left: 0 })] }) });
    expect(await screen.findByText(/còn 0 ngày/)).toBeInTheDocument();
  });

  it("mọi mốc đã chấp nhận → chúc mừng hoàn thành", async () => {
    setup({ i: internship({ status: "completed", milestones: [milestone({ status: "accepted" })] }) });
    expect(await screen.findByText("Bạn đã hoàn thành mọi mốc bắt buộc.")).toBeInTheDocument();
  });
});

describe("StudentHome — thông báo và các khối phụ", () => {
  it("giảng viên yêu cầu sửa → cảnh báo vàng kèm lý do", async () => {
    setup({ i: internship({ status: "revision_requested", decision_reason: "Thiếu MST" }) });
    expect(await screen.findByText("Giảng viên yêu cầu chỉnh sửa hồ sơ")).toBeInTheDocument();
    expect(screen.getByText("Thiếu MST")).toBeInTheDocument();
    expect(document.querySelector(".alert--warn")).not.toBeNull();
  });

  it("trạng thái khác có nhận xét → hiện dạng nhận xét thường", async () => {
    setup({ i: internship({ status: "approved", decision_reason: "Hồ sơ tốt" }) });
    expect(await screen.findByText("Nhận xét của giảng viên")).toBeInTheDocument();
    expect(document.querySelector(".alert--ok")).not.toBeNull();
  });

  it("không có nhận xét thì không có cảnh báo", async () => {
    setup();
    await screen.findByTestId("reg");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("cảnh báo rủi ro: mức nghiêm trọng đỏ, mức khác vàng, có lý do", async () => {
    setup({ flags: [
      { id: 1, severity: "critical", reason: "Trễ 2 mốc liên tiếp" },
      { id: 2, severity: "warning", reason: "Nhật ký thiếu tuần 3" },
      { id: 3, severity: "info", reason: "Sắp tới hạn" },
    ] });
    expect(await screen.findByText("Trễ 2 mốc liên tiếp")).toBeInTheDocument();
    expect(screen.getByText("Nghiêm trọng")).toBeInTheDocument();
    expect(document.querySelectorAll(".alert--bad")).toHaveLength(1);
    expect(document.querySelectorAll(".alert--warn")).toHaveLength(2);
  });

  it.each([["draft", false], ["submitted", false], ["revision_requested", false], ["approved", true], ["in_progress", true], ["completed", true]])(
    "đề cương: trạng thái %s → hiện = %s", async (status, shown) => {
      setup({ i: internship({ status }) });
      await screen.findByTestId("reg");
      expect(!!screen.queryByTestId("outline")).toBe(shown);
    });

  it("danh sách gia hạn chỉ hiện khi có yêu cầu", async () => {
    setup({ extensions: [{ id: 1 }] });
    expect(await screen.findByTestId("extensions")).toBeInTheDocument();
  });

  it("không có gia hạn → không hiện khối gia hạn", async () => {
    setup();
    await screen.findByTestId("reg");
    expect(screen.queryByTestId("extensions")).not.toBeInTheDocument();
  });
});
