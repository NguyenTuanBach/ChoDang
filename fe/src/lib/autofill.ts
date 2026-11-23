// AI đọc giấy tờ để tự điền (BE: /api/student/intake/auto, .../documents/{id}/extract, .../evidence/{id}/extract).
// Kho tạm trong trình duyệt: ngăn Trợ lý đặt gợi ý rồi chuyển trang; trang đích lấy ra (một lần) và điền vào form nháp, CHƯA lưu.

import { useCallback, useEffect, useRef, useState } from "react";

export type Suggestion = { value: string; confidence: number; source: string };
export type AutofillKind = "receipt_letter" | "completion_letter";

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

let pending: PendingAutofill | null = null;
const listeners = new Set<() => void>();

export function setPendingAutofill(value: PendingAutofill): void {
  pending = value;
  for (const listener of listeners) listener();
}

// Lấy và xóa (chỉ trang đúng loại giấy mới lấy).
export function takePendingAutofill(kind: AutofillKind): PendingAutofill | null {
  if (!pending || pending.kind !== kind) return null;
  const value = pending;
  pending = null;
  return value;
}

// Gợi ý đang chờ cho loại giấy này (lấy khi trang mở, và cả khi trang đang mở mà ngăn Trợ lý đặt gợi ý mới).
// `nonce` tăng mỗi lần có gợi ý mới: trang dùng làm `key` để dựng lại form. `clear()` khi người dùng đã lưu/xác nhận.
export function usePendingAutofill(kind: AutofillKind, onNew?: () => void): { value: PendingAutofill | null; nonce: number; clear: () => void } {
  // Khởi tạo chỉ đọc (StrictMode gọi hàm khởi tạo hai lần); xóa khỏi kho trong effect.
  const [value, setValue] = useState<PendingAutofill | null>(() => (pending?.kind === kind ? pending : null));
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
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, [kind]);
  const clear = useCallback(() => setValue(null), []);
  return { value, nonce, clear };
}

export const KIND_LABEL: Record<AutofillKind, string> = {
  receipt_letter: "Giấy tiếp nhận thực tập",
  completion_letter: "Giấy xác nhận / phiếu đánh giá của doanh nghiệp",
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
};

// Nút cần người dùng bấm sau khi AI điền: nhấp nháy cho tới khi bấm.
export const PULSE = "animate-pulse ring-2 ring-primary ring-offset-2";
