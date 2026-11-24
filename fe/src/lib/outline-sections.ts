// Đề cương gồm bốn phần bắt buộc (khớp `REQUIRED_SECTIONS` ở BE `outline_check.py`). Form nhập từng phần; khi nộp ghép thành một đoạn văn bản
// có tiêu đề "Mục tiêu: ...", nên BE vẫn lưu và kiểm tra đề cương dạng chữ như trước.

export const SECTIONS = [
  {
    key: "objective",
    label: "Mục tiêu",
    placeholder: "Ví dụ: Nắm quy trình phát triển web tại doanh nghiệp và hoàn thành tối thiểu hai module được giao.",
  },
  {
    key: "tasks",
    label: "Nhiệm vụ",
    placeholder: "Ví dụ: Phát triển API và giao diện module quản lý đơn hàng; viết kiểm thử; sửa lỗi theo yêu cầu của nhóm.",
  },
  {
    key: "plan",
    label: "Kế hoạch",
    placeholder: "Ví dụ: Tuần 1-2 làm quen hệ thống; tuần 3-8 phát triển tính năng; tuần 9-12 kiểm thử và báo cáo.",
  },
  {
    key: "results",
    label: "Kết quả dự kiến",
    placeholder: "Ví dụ: Hoàn thành ba tính năng kèm kiểm thử tự động và báo cáo cuối kỳ.",
  },
] as const;

export type SectionKey = (typeof SECTIONS)[number]["key"];
export type SectionValues = Record<SectionKey, string>;

export const EMPTY_SECTIONS: SectionValues = { objective: "", tasks: "", plan: "", results: "" };

/** Ghép các phần đã nhập thành văn bản gửi BE. Phần để trống thì bỏ cả tiêu đề, để BE báo đúng phần còn thiếu. */
export function composeOutline(values: SectionValues): string {
  return SECTIONS.filter((s) => values[s.key].trim() !== "")
    .map((s) => `${s.label}:\n${values[s.key].trim()}`)
    .join("\n\n");
}

/** Tách văn bản đề cương cũ về từng phần để sửa lại. Không nhận ra tiêu đề nào thì đưa cả văn bản vào "Mục tiêu". */
export function parseOutline(text: string): SectionValues {
  const out: SectionValues = { ...EMPTY_SECTIONS };
  let current: SectionKey | null = null;
  let matched = false;
  const heading = new RegExp(`^\\s*(${SECTIONS.map((s) => s.label).join("|")})\\s*:\\s*(.*)$`, "i");
  for (const line of text.split("\n")) {
    const m = heading.exec(line);
    if (m) {
      matched = true;
      current = SECTIONS.find((s) => s.label.toLowerCase() === m[1].toLowerCase())!.key;
      out[current] = m[2];
    } else if (current) {
      out[current] += (out[current] ? "\n" : "") + line;
    }
  }
  if (!matched) return { ...EMPTY_SECTIONS, objective: text.trim() };
  for (const s of SECTIONS) out[s.key] = out[s.key].trim();
  return out;
}
