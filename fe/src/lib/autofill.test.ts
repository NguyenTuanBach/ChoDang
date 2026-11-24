import { afterEach, describe, expect, it } from "vitest";
import { setPendingAutofill, takePendingAutofill, toPending, type AutofillResult } from "./autofill";

const RESULT: AutofillResult = {
  kind: "outline",
  target_page: "outline",
  document_id: null,
  evidence_id: null,
  fields: { objective: { value: "Mục tiêu", confidence: 0.9, source: "" } },
  notes: "",
  warnings: [],
};

afterEach(() => {
  takePendingAutofill("outline");
});

describe("autofill store", () => {
  it("toPending giữ loại giấy, mã và các trường của kết quả BE", () => {
    expect(toPending(RESULT)).toEqual({ kind: "outline", documentId: null, evidenceId: null, fields: RESULT.fields, warnings: [] });
  });

  it("gợi ý chỉ được lấy một lần, và chỉ đúng loại; đặt lại thì lấy được lần nữa", () => {
    setPendingAutofill(toPending(RESULT));
    expect(takePendingAutofill("receipt_letter")).toBeNull(); // sai loại: không lấy, không mất
    expect(takePendingAutofill("outline")?.fields.objective.value).toBe("Mục tiêu");
    expect(takePendingAutofill("outline")).toBeNull(); // đã lấy rồi
    setPendingAutofill(toPending(RESULT)); // bấm lại thẻ / trợ lý mở lại trang
    expect(takePendingAutofill("outline")).not.toBeNull();
  });
});
