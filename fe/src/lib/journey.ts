// Hành trình thực tập của sinh viên (5 bước) suy ra từ trạng thái hồ sơ. Hàm thuần: không gọi API.

export type StepState = "done" | "current" | "todo" | "failed";
export type JourneyStep = { key: string; label: string; state: StepState };

const STEPS = [
  { key: "profile", label: "Hồ sơ" },
  { key: "outline", label: "Đề cương" },
  { key: "internship", label: "Thực tập" },
  { key: "finish", label: "Kết thúc" },
  { key: "credit", label: "Tín chỉ" },
] as const;

// Chỉ số bước hiện tại và có lỗi (bị từ chối/không công nhận) hay đã hoàn tất hay không.
const POSITION: Record<string, { index: number; failed?: boolean; finished?: boolean }> = {
  draft: { index: 0 },
  revision_requested: { index: 0 },
  submitted: { index: 0 },
  rejected: { index: 0, failed: true },
  confirmed: { index: 1 },
  in_progress: { index: 2 },
  pending_credit: { index: 4 },
  credit_review: { index: 4 },
  completed: { index: 4, finished: true },
  closed_no_credit: { index: 4, failed: true },
};

export function journey(status: string | null | undefined): JourneyStep[] {
  const position = status ? POSITION[status] : undefined;
  const index = position?.index ?? 0;
  return STEPS.map((step, i) => {
    let state: StepState = i < index ? "done" : i === index ? "current" : "todo";
    if (i === index && position?.failed) state = "failed";
    if (i === index && position?.finished) state = "done";
    return { ...step, state };
  });
}
