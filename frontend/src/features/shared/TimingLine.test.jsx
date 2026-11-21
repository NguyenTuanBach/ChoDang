import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TimingLine } from "./Assistant";

describe("TimingLine", () => {
  it("báo đã gọi LLM kèm model và thời gian", () => {
    render(<TimingLine m={{ outcome: "answered", timing: { llm_called: true, llm_ms: 1234, total_ms: 3100, model: "gpt-4o" } }} />);
    expect(screen.getByText("Đã gọi gpt-4o · LLM 1.2s · tổng 3.1s")).toBeInTheDocument();
  });

  it.each([
    ["smalltalk", "lời chào"], ["refused", "bị guardrail chặn"], ["not_found", "không có đoạn quy định phù hợp"],
  ])("không gọi LLM khi %s", (outcome, reason) => {
    render(<TimingLine m={{ outcome, timing: { llm_called: false, llm_ms: 0, total_ms: 450, model: "" } }} />);
    expect(screen.getByText(`Không gọi LLM (${reason}) · tổng 0.5s`)).toBeInTheDocument();
  });

  it("không hiện gì khi thiếu thông tin", () => {
    const { container } = render(<TimingLine m={{ outcome: "answered" }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
