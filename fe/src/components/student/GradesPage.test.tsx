import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import GradesPage from "./GradesPage";

const LMS = { student_code: "SV0008", record: null, prerequisites: { met: false, missing: ["Nhập môn (CS101): chưa có điểm"] } };

afterEach(() => vi.unstubAllGlobals());

describe("GradesPage", () => {
  it("không hiện điều kiện học phần, dù chưa đủ điều kiện hay chưa có hồ sơ", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/lms/me") return new Response(JSON.stringify(LMS));
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GradesPage />);
    await screen.findByText("Tín chỉ từ thực tập");
    expect(screen.queryByText("Điều kiện để học học phần thực tập")).toBeNull();
    expect(screen.queryByText("Chưa đủ điều kiện")).toBeNull();
    expect(screen.queryByText(/Nhập môn \(CS101\)/)).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1); // chỉ gọi LMS, không còn gọi hồ sơ chỉ để ẩn thẻ
  });
});
