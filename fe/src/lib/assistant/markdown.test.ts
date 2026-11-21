import { describe, expect, it } from "vitest";
import { hideIncompleteCite, parseInline, parseMarkdown } from "./markdown";

describe("parseInline", () => {
  it("nhận diện [cite:id] kể cả id có dấu hai chấm và chấm", () => {
    expect(parseInline("Nộp [cite:QC-01:v1.0:d5:k2] nhé")).toEqual([
      { kind: "text", text: "Nộp " },
      { kind: "cite", chunkId: "QC-01:v1.0:d5:k2" },
      { kind: "text", text: " nhé" },
    ]);
  });

  it("đậm, nghiêng, mã, liên kết", () => {
    const nodes = parseInline("**đậm [cite:a]** và *nghiêng* và `x` và [trang](https://a.vn/p?q=1)");
    expect(nodes[0]).toEqual({
      kind: "bold",
      children: [
        { kind: "text", text: "đậm " },
        { kind: "cite", chunkId: "a" },
      ],
    });
    expect(nodes.map((node) => node.kind)).toEqual(["bold", "text", "italic", "text", "code", "text", "link"]);
  });

  it("không biến liên kết javascript: thành liên kết", () => {
    const nodes = parseInline("[bấm](javascript:alert(1))");
    expect(nodes.some((node) => node.kind === "link")).toBe(false);
  });

  it("HTML thô giữ nguyên là văn bản", () => {
    expect(parseInline("<img src=x onerror=alert(1)>")).toEqual([{ kind: "text", text: "<img src=x onerror=alert(1)>" }]);
  });
});

describe("parseMarkdown", () => {
  it("tách tiêu đề, đoạn, danh sách, trích dẫn, khối mã", () => {
    const blocks = parseMarkdown(
      ["## Kết luận", "Dòng 1", "dòng 2", "", "- a", "- b", "", "1. x", "2) y", "", "> quote", "", "```", "code <b>", "```"].join("\n"),
    );
    expect(blocks.map((block) => block.kind)).toEqual(["heading", "paragraph", "list", "list", "quote", "code"]);
    expect(blocks[1]).toMatchObject({ children: [{ kind: "text" }, { kind: "br" }, { kind: "text" }] });
    expect(blocks[2]).toMatchObject({ ordered: false });
    expect(blocks[2]).toMatchObject({ items: [expect.any(Array), expect.any(Array)] });
    expect(blocks[3]).toMatchObject({ ordered: true });
    expect(blocks[5]).toEqual({ kind: "code", text: "code <b>" });
  });

  it("khối mã chưa đóng (đang stream) vẫn dựng được", () => {
    expect(parseMarkdown("```\nabc")).toEqual([{ kind: "code", text: "abc" }]);
  });

  it("văn bản rỗng cho danh sách rỗng", () => {
    expect(parseMarkdown("")).toEqual([]);
  });
});

describe("hideIncompleteCite", () => {
  it("ẩn dấu trích dẫn dở dang ở cuối", () => {
    expect(hideIncompleteCite("Nộp [cite:QC-0")).toBe("Nộp ");
    expect(hideIncompleteCite("Nộp [ci")).toBe("Nộp ");
    expect(hideIncompleteCite("Nộp [cite:a]")).toBe("Nộp [cite:a]");
    expect(hideIncompleteCite("Nộp [1]")).toBe("Nộp [1]");
  });
});
