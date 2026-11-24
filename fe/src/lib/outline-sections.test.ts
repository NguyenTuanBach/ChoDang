import { describe, expect, it } from "vitest";
import { composeOutline, EMPTY_SECTIONS, parseOutline } from "./outline-sections";

const FULL = { objective: "Học web", tasks: "Làm API", plan: "Tuần 1-12", results: "Ba tính năng" };

describe("outline-sections", () => {
  it("ghép bốn phần có tiêu đề, theo đúng thứ tự", () => {
    expect(composeOutline(FULL)).toBe("Mục tiêu:\nHọc web\n\nNhiệm vụ:\nLàm API\n\nKế hoạch:\nTuần 1-12\n\nKết quả dự kiến:\nBa tính năng");
  });

  it("phần để trống thì bỏ cả tiêu đề để BE báo thiếu đúng phần", () => {
    const text = composeOutline({ ...FULL, tasks: "   ", plan: "" });
    expect(text).toContain("Mục tiêu:");
    expect(text).not.toContain("Nhiệm vụ");
    expect(text).not.toContain("Kế hoạch");
    expect(text).toContain("Kết quả dự kiến:");
  });

  it("tách ngược văn bản đã ghép về đúng từng phần (kể cả nhiều dòng)", () => {
    const values = { ...FULL, plan: "Tuần 1-2 làm quen\nTuần 3-12 phát triển" };
    expect(parseOutline(composeOutline(values))).toEqual(values);
  });

  it("văn bản cũ không có tiêu đề thì đưa vào Mục tiêu", () => {
    expect(parseOutline("Em muốn học hỏi thêm về lập trình web.")).toEqual({ ...EMPTY_SECTIONS, objective: "Em muốn học hỏi thêm về lập trình web." });
  });

  it("nhận tiêu đề không phân biệt hoa thường", () => {
    expect(parseOutline("mục tiêu: A\nNHIỆM VỤ: B").tasks).toBe("B");
  });
});
