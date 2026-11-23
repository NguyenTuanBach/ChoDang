// Kiểu dữ liệu trả về từ BE (khớp các endpoint trong be/src/vin15/presentation/controller).

export type Internship = {
  id: number;
  user_id: number;
  cohort: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  mode: "onsite" | "remote" | "hybrid";
  company_name: string;
  company_tax_code: string;
  company_address: string;
  position: string;
  mentor_name: string;
  mentor_email: string;
  mentor_phone: string;
  job_description: string;
  field_confirmations: Record<string, string>;
  version: number;
  decision_reason: string;
  student_name: string;
  student_email: string;
  student_code: string | null;
  lecturer_id: number | null;
  lecturer_name: string | null;
};

export type Milestone = {
  id: number;
  code: string;
  name: string;
  due_date: string;
  status: string;
  stored_status: string;
  days_left: number;
  next_action: string;
  note: string;
  submittable: boolean;
};

export type Outline = {
  id: number;
  version: number;
  content: string;
  outcome_codes: string[];
  status: string;
  feedback: string;
  submitted_at: string;
};

/** Một việc trong nhật ký tuần; `done` = đã hoàn thành (chưa xong thì chuyển sang tuần sau). */
export type PlanItem = { text: string; done: boolean };

export type Journal = {
  id: number;
  week_start: string;
  content: string;
  plan_items: PlanItem[];
  blockers: string;
  /** Gợi ý lịch do AI (rỗng nếu sinh viên không hỏi). */
  ai_advice: string;
  submitted_at: string;
  lecturer_comment: string;
};

export type Evidence = {
  id: number;
  milestone_id: number;
  milestone_code: string;
  title: string;
  filename: string;
  mime: string;
  size_bytes: number;
  status: string;
  reviewer_comment: string;
  submitted_at: string;
  reviewed_at: string | null;
};

export type Attachment = { id: number; filename: string; mime: string; size_bytes: number };

export type RequestItem = {
  id: number;
  internship_id: number;
  kind: "milestone_extension" | "exception";
  status: string;
  reason: string;
  milestone_code: string | null;
  new_due_date: string | null;
  exception_type_code: string | null;
  exception_type_name: string | null;
  affects_credit: boolean;
  decision_reason: string;
  student_name: string;
  created_at: string;
  attachments: Attachment[];
};

export type Flag = {
  id: number;
  internship_id: number;
  kind: string;
  severity: "info" | "warning" | "critical";
  status: string;
  reason: string;
  suggestion: string;
  created_by_kind: string;
  created_at: string;
  student_name: string;
  decision_reason: string;
};

export type Suggestion = {
  id: number;
  subject_kind: string;
  subject_id: number;
  summary: string;
  details: { outcome_matches?: { code: string; covered: boolean; note: string }[]; concerns?: string[]; evidence_notes?: string[] };
  created_at: string;
};

export type DocumentItem = { id: number; filename: string; mime: string; size_bytes: number; uploaded_at: string };

export type CreditItem = { code: string; label: string; met: boolean; value: string; threshold: string };

export type CreditView = {
  items: CreditItem[];
  all_met: boolean;
  assessment: { status: string; lecturer_note: string; admin_reason: string } | null;
};

export type Citation = {
  chunk_id: string;
  doc_title: string;
  version: string;
  article_no: string;
  clause_no: string | null;
  text: string;
  is_sample: boolean;
};

export type Check = { code: string; label: string; ok: boolean; level: "error" | "warning"; detail: string; citation: Citation | null };

export type Outcome = { id: number; cohort: string; code: string; description: string };

export type InternshipDetail = {
  internship: Internship | null;
  documents: DocumentItem[];
  milestones: Milestone[];
  outlines: Outline[];
  journals: Journal[];
  evidence: Evidence[];
  requests: RequestItem[];
  flags: Flag[];
  suggestions: Suggestion[];
  credit?: CreditView;
  outcomes?: Outcome[];
  checks?: Check[];
};

export type ListRow = {
  id: number;
  cohort: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  company_name: string;
  student_name: string;
  student_email: string;
  student_code: string | null;
  lecturer_name: string | null;
  overdue_milestones: number;
  submitted_milestones: number;
  open_flags: number;
};

export type QueueItem = {
  kind: string;
  internship_id: number;
  ref_id: number;
  student_name: string;
  title: string;
  since: string | null;
  due_date: string | null;
  severity: string | null;
  priority: number;
};

export type Account = {
  id: number;
  email: string;
  full_name: string;
  role: "student" | "lecturer" | "admin";
  status: "invited" | "active" | "revoked";
  student_code: string | null;
  advisor_id: number | null;
  /** Thời điểm mời (hoặc mời lại) gần nhất. */
  invited_at: string | null;
  /** Lời mời còn "invited" nhưng đã quá 3 giờ (BE tính). */
  invitation_expired: boolean;
};

export type NotificationItem = { id: number; kind: string; title: string; body: string; link: string; created_at: string; read_at: string | null };

export type ExceptionType = { code: string; name: string; affects_credit: boolean; active: boolean };

export type MilestoneTemplate = { code: string; name: string; anchor: "start" | "mid" | "end"; offset_days: number };

export type Course = { code: string; name: string; credits: number; kind: "regular" | "internship" };

export type LmsStudent = { student_code: string; full_name: string; credits: number };

export type LmsRecord = {
  student_code: string | null;
  record: {
    student_code: string;
    full_name: string;
    total_credits: number;
    grades: { course_code: string; course_name: string; credits: number; score: number; term: string }[];
    credits: { course_code: string; course_name: string; credits: number; source: string; posted_at: string }[];
  } | null;
  prerequisites: { met: boolean; missing: string[] };
};

export type SyncJob = {
  id: number;
  internship_id: number;
  student_code: string;
  course_code: string;
  credits: number;
  status: "pending" | "synced" | "failed";
  attempts: number;
  last_error: string;
  student_name: string;
};

export type Dashboard = {
  internships_by_status: { status: string; n: number }[];
  milestones_by_status: { status: string; n: number }[];
  late_internships: number;
  active_internships: number;
  flags: { severity: string; status: string; n: number }[];
  decision_times: { kind: string; count: number; median_days: number | null }[];
  credit_outcomes: { status: string; n: number }[];
  sync_jobs: { status: string; n: number }[];
};

export type AuditEvent = {
  id: number;
  at: string;
  actor_kind: string;
  actor_role: string;
  actor_name: string | null;
  entity: string;
  entity_id: number | null;
  action: string;
  reason: string;
};

export type PolicyVersion = {
  id: string;
  doc_code: string;
  doc_title: string;
  version_label: string;
  effective_from: string;
  effective_to: string | null;
  status: "draft" | "published" | "superseded";
  is_sample: boolean;
  chunk_count: number;
  embedded_count: number; // < chunk_count: phần còn lại chỉ tìm được bằng từ khóa
};

export type PolicyChunk = { chunk_id: string; article_no: string; clause_no: string | null; heading: string; text: string };
export type PolicyPreview = { version: PolicyVersion; chunks: PolicyChunk[] };
export type PolicyIngestResult = { version: PolicyVersion; chunk_count: number; embedded_count: number };
export type PolicyExtractResult = { filename: string; text: string; chunk_count: number; warning: string | null };
export type PolicyEmbedResult = { version: PolicyVersion; embedded_now: number; agent_enabled: boolean };
