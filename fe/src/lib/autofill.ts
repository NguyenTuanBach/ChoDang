// AI đọc giấy tờ để tự điền (BE: /api/student/intake/auto, .../documents/{id}/extract, .../evidence/{id}/extract).
// Kho tạm trong trình duyệt: ngăn Trợ lý đặt gợi ý rồi chuyển trang; trang đích lấy ra (một lần) và điền vào form nháp, CHƯA lưu.

import { useCallback, useEffect, useRef, useState } from "react";

export type Suggestion = { value: string; confidence: number; source: string };
export type AutofillKind = "receipt_letter" | "completion_letter" | "outline";

export type AutofillResult = {
  kind: AutofillKind;
  target_page: string;
  document_id: number | null;
  evidence_id: number | null;
  fields: Record<string, Suggestion>;
  notes: string;
  warnings: string[];
};

export type PendingAutofill = { kind: AutofillKind; documentId: number | null; evidenceId: number | null; fields: Record<string, Suggestion>; warnings: string[] };

// Kho đặt ở `globalThis` để mọi bản của module này (kể cả khi Next tải nóng một phần file) dùng chung một kho:
// ngăn Trợ lý và trang đích không bao giờ giữ hai kho riêng.
type AutofillStore = { pending: PendingAutofill | null; listeners: Set<() => void> };
const holder = globalThis as typeof globalThis & { __vin15Autofill?: AutofillStore };
const store: AutofillStore = (holder.__vin15Autofill ??= { pending: null, listeners: new Set() });

export function setPendingAutofill(value: PendingAutofill): void {
  store.pending = value;
  for (const listener of store.listeners) listener();
}

/** Gợi ý chờ điền suy ra từ kết quả BE trả về (dùng lại khi thẻ trong Trợ lý được áp dụng lần nữa). */
export function toPending(result: AutofillResult): PendingAutofill {
  return { kind: result.kind, documentId: result.document_id, evidenceId: result.evidence_id, fields: result.fields, warnings: result.warnings ?? [] };
}

// Lấy và xóa (chỉ trang đúng loại giấy mới lấy).
export function takePendingAutofill(kind: AutofillKind): PendingAutofill | null {
  if (!store.pending || store.pending.kind !== kind) return null;
  const value = store.pending;
  store.pending = null;
  return value;
}

// Gợi ý đang chờ cho loại giấy này (lấy khi trang mở, và cả khi trang đang mở mà ngăn Trợ lý đặt gợi ý mới).
// `nonce` tăng mỗi lần có gợi ý mới: trang dùng làm `key` để dựng lại form. `clear()` khi người dùng đã lưu/xác nhận.
export function usePendingAutofill(kind: AutofillKind, onNew?: () => void): { value: PendingAutofill | null; nonce: number; clear: () => void } {
  // Khởi tạo chỉ đọc (StrictMode gọi hàm khởi tạo hai lần); xóa khỏi kho trong effect.
  const [value, setValue] = useState<PendingAutofill | null>(() => (store.pending?.kind === kind ? store.pending : null));
  const [nonce, setNonce] = useState(0);
  const onNewRef = useRef(onNew);
  useEffect(() => {
    onNewRef.current = onNew;
  }, [onNew]);
  useEffect(() => {
    takePendingAutofill(kind);
  }, [kind]);
  useEffect(() => {
    const listener = () => {
      const next = takePendingAutofill(kind);
      if (!next) return;
      setValue(next);
      setNonce((n) => n + 1);
      onNewRef.current?.();
    };
    store.listeners.add(listener);
    return () => {
      store.listeners.delete(listener);
    };
  }, [kind]);
  const clear = useCallback(() => setValue(null), []);
  return { value, nonce, clear };
}

export const KIND_LABEL: Record<AutofillKind, string> = {
  receipt_letter: "Giấy tiếp nhận thực tập",
  completion_letter: "Giấy xác nhận / phiếu đánh giá của doanh nghiệp",
  outline: "Đề cương thực tập",
};

// Nhãn trường để hiển thị gợi ý (hồ sơ + giấy xác nhận).
export const FIELD_LABEL: Record<string, string> = {
  company_name: "Tên doanh nghiệp",
  company_tax_code: "Mã số thuế",
  company_address: "Địa chỉ doanh nghiệp",
  position: "Vị trí thực tập",
  department: "Phòng ban / bộ phận",
  mentor_name: "Người hướng dẫn",
  mentor_title: "Chức vụ người hướng dẫn",
  mentor_email: "Email người hướng dẫn",
  mentor_phone: "SĐT người hướng dẫn",
  job_description: "Mô tả công việc",
  start_date: "Ngày bắt đầu",
  end_date: "Ngày kết thúc",
  mode: "Hình thức thực tập",
  receipt_letter_number: "Số hiệu giấy tiếp nhận",
  receipt_letter_date: "Ngày ký giấy tiếp nhận",
  receipt_signer_name: "Người ký giấy tiếp nhận",
  receipt_signer_title: "Chức vụ người ký",
  student_name: "Họ tên sinh viên (trên giấy)",
  student_code: "Mã sinh viên (trên giấy)",
  actual_start_date: "Ngày bắt đầu thực tế",
  actual_end_date: "Ngày kết thúc thực tế",
  result_grade: "Kết quả / xếp loại",
  score: "Điểm",
  company_comment: "Nhận xét của doanh nghiệp",
  signer_name: "Người ký xác nhận",
  signer_title: "Chức vụ người ký",
  letter_number: "Số hiệu văn bản",
  letter_date: "Ngày ký văn bản",
  has_stamp: "Có chữ ký / dấu",
  objective: "Mục tiêu",
  tasks: "Nhiệm vụ",
  plan: "Kế hoạch",
  results: "Kết quả dự kiến",
};

// Nút cần người dùng bấm sau khi AI điền: nhấp nháy cho tới khi bấm.
export const PULSE = "animate-pulse ring-2 ring-primary ring-offset-2";
