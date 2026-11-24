"use client";

import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { PULSE, usePendingAutofill, type PendingAutofill, type Suggestion } from "@/lib/autofill";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { MODE_LABEL, fmtDate } from "@/lib/labels";
import type { Check, InternshipDetail } from "@/lib/types";
import { Async, Badge, Button, Card, DropZone, Empty, ErrorToast, Field, OkText, Page, Row, StatusBadge } from "@/components/ui/ui";
import DownloadDoc from "./DownloadDoc";
import NoticeCard from "@/components/ui/notice-card";
import EvidencePreviewDialog from "./EvidencePreviewDialog";

type Form = {
  company_name: string;
  company_tax_code: string;
  company_address: string;
  position: string;
  mentor_name: string;
  mentor_email: string;
  mentor_phone: string;
  job_description: string;
  start_date: string;
  end_date: string;
  mode: "onsite" | "remote" | "hybrid";
  department: string;
  mentor_title: string;
  receipt_letter_number: string;
  receipt_letter_date: string;
  receipt_signer_name: string;
  receipt_signer_title: string;
};

const MODES = ["onsite", "remote", "hybrid"] as const;
const DATE_KEYS = ["start_date", "end_date", "receipt_letter_date"] as const;

const FIELDS: { key: keyof Form; label: string; type?: string; wide?: boolean }[] = [
  { key: "company_name", label: "Tên doanh nghiệp" },
  { key: "company_tax_code", label: "Mã số thuế (10 hoặc 13 số)" },
  { key: "company_address", label: "Địa chỉ doanh nghiệp" },
  { key: "position", label: "Vị trí thực tập" },
  { key: "department", label: "Phòng ban / bộ phận" },
  { key: "mentor_name", label: "Người hướng dẫn tại doanh nghiệp" },
  { key: "mentor_title", label: "Chức vụ người hướng dẫn" },
  { key: "mentor_email", label: "Email người hướng dẫn", type: "email" },
  { key: "mentor_phone", label: "Số điện thoại người hướng dẫn" },
  { key: "start_date", label: "Ngày bắt đầu", type: "date" },
  { key: "end_date", label: "Ngày kết thúc", type: "date" },
  { key: "job_description", label: "Mô tả công việc", wide: true },
];

// Thông tin của chính tờ giấy tiếp nhận (không phải dữ liệu thực tập): hiện trong thẻ giấy tiếp nhận.
const RECEIPT_FIELDS: { key: keyof Form; label: string; type?: string }[] = [
  { key: "receipt_letter_number", label: "Số hiệu giấy" },
  { key: "receipt_letter_date", label: "Ngày ký giấy", type: "date" },
  { key: "receipt_signer_name", label: "Người ký giấy" },
  { key: "receipt_signer_title", label: "Chức vụ người ký" },
];
const ALL_FIELDS = [...FIELDS, ...RECEIPT_FIELDS];

const EDITABLE = ["draft", "revision_requested"];
// Sau khi nộp: chỉ phần cá nhân còn sửa được (khớp BE `PERSONAL_FIELDS` / `PERSONAL_EDITABLE_STATUSES`); thông tin công ty và thời gian bị khóa.
const PERSONAL_EDITABLE = ["submitted", "confirmed", "in_progress"];
const PERSONAL_KEYS: ReadonlySet<string> = new Set(["position", "job_description"]);
const EMPTY: Form = {
  company_name: "",
  company_tax_code: "",
  company_address: "",
  position: "",
  mentor_name: "",
  mentor_email: "",
  mentor_phone: "",
  job_description: "",
  start_date: "",
  end_date: "",
  mode: "onsite",
  department: "",
  mentor_title: "",
  receipt_letter_number: "",
  receipt_letter_date: "",
  receipt_signer_name: "",
  receipt_signer_title: "",
};

export default function InternshipForm() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  // `key`: chưa có hồ sơ coi như phiên bản 1, để tạo nháp (lưu hoặc tải giấy) không dựng lại form và mất phần đang gõ.
  // Gợi ý do ngăn Trợ lý đặt (đính kèm giấy trong chat): điền vào form nháp, chưa lưu; có gợi ý mới thì tải lại hồ sơ (có thể vừa tạo nháp).
  const auto = usePendingAutofill("receipt_letter", state.reload);
  return (
    <Page title="Hồ sơ thực tập">
      <Async state={state}>
        {(d) => <Editor key={`${d.internship?.version ?? 1}-${auto.nonce}`} detail={d} reload={state.reload} autofill={auto.value} onAutofillSaved={auto.clear} />}
      </Async>
    </Page>
  );
}

function applySuggestions(form: Form, fields: Record<string, Suggestion>): { form: Form; keys: string[] } {
  const next = { ...form };
  const keys: string[] = [];
  for (const [key, s] of Object.entries(fields)) {
    if (!(key in next)) continue;
    if (key === "mode") {
      if (!(MODES as readonly string[]).includes(s.value)) continue;
      next.mode = s.value as Form["mode"];
    } else {
      (next as Record<string, string>)[key] = (DATE_KEYS as readonly string[]).includes(key) ? s.value.slice(0, 10) : s.value;
    }
    keys.push(key);
  }
  return { form: next, keys };
}

function Editor({
  detail,
  reload,
  autofill,
  onAutofillSaved,
}: {
  detail: InternshipDetail;
  reload: () => void;
  autofill: PendingAutofill | null;
  onAutofillSaved: () => void;
}) {
  const row = detail.internship;
  const editableAtStart = !row || EDITABLE.includes(row.status);
  const [form, setForm] = useState<Form>(() => {
    const base: Form = {
    company_name: row?.company_name ?? "",
    company_tax_code: row?.company_tax_code ?? "",
    company_address: row?.company_address ?? "",
    position: row?.position ?? "",
    mentor_name: row?.mentor_name ?? "",
    mentor_email: row?.mentor_email ?? "",
    mentor_phone: row?.mentor_phone ?? "",
    job_description: row?.job_description ?? "",
    start_date: row?.start_date ?? "",
    end_date: row?.end_date ?? "",
    mode: row?.mode ?? "onsite",
    department: row?.department ?? "",
    mentor_title: row?.mentor_title ?? "",
    receipt_letter_number: row?.receipt_letter_number ?? "",
    receipt_letter_date: row?.receipt_letter_date ?? "",
    receipt_signer_name: row?.receipt_signer_name ?? "",
    receipt_signer_title: row?.receipt_signer_title ?? "",
    };
    return autofill && editableAtStart ? applySuggestions(base, autofill.fields).form : base;
  });
  const [confirmations, setConfirmations] = useState<Record<string, string>>(() =>
    autofill && editableAtStart ? Object.fromEntries(applySuggestions(EMPTY, autofill.fields).keys.map((k) => [k, "ai_confirmed"])) : {},
  );
  const [warnings, setWarnings] = useState<string[]>(autofill?.warnings ?? []);
  // Nút Lưu nhấp nháy sau khi AI điền, cho tới khi người dùng bấm.
  const [pulseSave, setPulseSave] = useState(Boolean(autofill && editableAtStart));
  // Tệp vừa chọn, chờ xem lại trong popup rồi mới tải lên.
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const saveRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (pulseSave) saveRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    // chỉ khi vừa mở trang kèm gợi ý
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [suggestions, setSuggestions] = useState<Record<string, Suggestion> | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [checks, setChecks] = useState<Check[]>(detail.checks ?? []);
  const [message, setMessage] = useState<string | null>(null);
  const save = useAction();
  const submit = useAction(reload);
  const docs = useAction(reload);
  const extract = useAction();

  const editable = !row || EDITABLE.includes(row.status);
  // Hồ sơ đã nộp mà còn hiệu lực: mở riêng phần cá nhân (vị trí, mô tả công việc, hình thức).
  const personalOnly = !editable && row !== null && row !== undefined && PERSONAL_EDITABLE.includes(row.status);
  const canEdit = (key: string) => editable || (personalOnly && (PERSONAL_KEYS.has(key) || key === "mode"));
  const personal = useAction(reload);
  // Phòng thủ: chưa có hồ sơ thì BE có thể không có danh sách giấy.
  const documents = detail.documents ?? [];
  // Mỗi hồ sơ chỉ có MỘT giấy tiếp nhận (tải giấy mới thì thay giấy cũ); hồ sơ cũ còn nhiều giấy thì chỉ hiện giấy mới nhất.
  const doc = documents.length > 0 ? documents[documents.length - 1] : null;
  // Khối tải giấy tiếp nhận: dùng ở cả thẻ "Thông tin thực tập" và thẻ giấy tiếp nhận (cùng một tệp, cùng một popup xem lại).
  const uploadRow = doc ? (
    <Row>
      <DownloadDoc href={`/api/documents/${doc.id}/download`} name={doc.filename} />
      <span>({fmtDate(doc.uploaded_at)})</span>
    </Row>
  ) : (
    <DropZone label="Tải giấy tiếp nhận" accept=".pdf,.png,.jpg,.jpeg" disabled={!editable || docs.busy || extract.busy} onFile={(file) => setPreviewFile(file)}>
      {editable ? "Chưa tải giấy tiếp nhận (PDF, ảnh chụp hoặc bản scan). Bấm vào đây hoặc kéo thả tệp để tải lên, AI sẽ tự điền các trường." : "Hồ sơ đã nộp nên không tải thêm giấy tiếp nhận."}
    </DropZone>
  );

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setConfirmations((c) => ({ ...c, [key]: "manual" }));
  }

  function payload() {
    return {
      ...form,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      receipt_letter_date: form.receipt_letter_date || null,
      confirmations,
    };
  }

  async function saveDraft() {
    setMessage(null);
    setPulseSave(false);
    const ok = await save.run(async () => {
      const result = await send<{ checks: Check[] }>("PUT", "/api/student/internship", payload());
      setChecks(result.checks);
    });
    if (ok) {
      setMessage("Đã lưu bản nháp.");
      onAutofillSaved();
      if (!row) reload();
    }
  }

  async function submitIt() {
    await save.run(async () => {
      await send("PUT", "/api/student/internship", payload());
    });
    await submit.run(() => send("POST", "/api/student/internship/submit"));
  }

  async function runExtract(documentId: number) {
    await extract.run(async () => {
      const result = await send<{ fields: Record<string, Suggestion>; notes: string; warnings?: string[] }>("POST", `/api/student/internship/documents/${documentId}/extract`);
      setSuggestions(result.fields);
      setNote(result.notes || (Object.keys(result.fields).length === 0 ? "AI không đọc được trường nào; hãy nhập tay." : null));
      setWarnings(result.warnings ?? []);
      // Tự điền thẳng vào form (chưa lưu): người dùng kiểm tra rồi bấm "Lưu bản nháp".
      if (Object.keys(result.fields).length > 0) accept(result.fields);
    });
  }

  function accept(picked: Record<string, Suggestion>) {
    const { keys } = applySuggestions(EMPTY, picked);
    setForm((f) => applySuggestions(f, picked).form);
    setConfirmations((c) => ({ ...c, ...Object.fromEntries(keys.map((k) => [k, "ai_confirmed"])) }));
    setSuggestions((all) => {
      if (!all) return all;
      const rest = { ...all };
      for (const key of Object.keys(picked)) delete rest[key];
      return Object.keys(rest).length > 0 ? rest : null;
    });
    if (keys.length > 0) setPulseSave(true);
  }

  async function uploadDoc(file: File) {
    let id: number | null = null;
    const ok = await docs.run(async () => {
      id = (await upload<{ id: number }>("/api/student/internship/documents", file)).id;
    });
    // Tải xong thì AI đọc giấy ngay và tự điền form, không hỏi lại.
    if (ok && id !== null) await runExtract(id);
  }

  const blocking = checks.filter((c) => !c.ok && c.level === "error");
  // Mọi ô của hồ sơ đều bắt buộc (dấu *): còn ô trống thì chưa cho nộp. Backend vẫn kiểm riêng các trường cốt lõi.
  const missing = ALL_FIELDS.filter((f) => !String(form[f.key] ?? "").trim());
  // Chỉ hiện các mục chưa đạt (thiếu hoặc sai); mục đạt không liệt kê.
  const problems = checks.filter((c) => !c.ok);
  // Kết quả kiểm tra là của bản ĐÃ LƯU. Form khác bản đã lưu (vd AI vừa điền, hoặc đang sửa) thì kết quả cũ chưa phản ánh.
  const savedRow = (row ?? {}) as unknown as Record<string, unknown>;
  const dirty = row ? [...ALL_FIELDS.map((f) => f.key), "mode"].some((k) => String(form[k as keyof Form] ?? "") !== String(savedRow[k] ?? "")) : false;

  return (
    <>
      {row && (
        <Card>
          <Row>
            <StatusBadge kind="internship" value={row.status} />
            <span>
              Phiên bản {row.version} · Giảng viên: {row.lecturer_name ?? "chưa được phân công"}
            </span>
          </Row>
          {row.decision_reason && <p>Lý do từ giảng viên: {row.decision_reason}</p>}
          {!editable && (
            <p>
              {personalOnly
                ? "Hồ sơ đã nộp: thông tin công ty và thời gian đã khóa; bạn chỉ sửa được vị trí, mô tả công việc và hình thức thực tập."
                : "Hồ sơ đã kết thúc nên không sửa được."}
            </p>
          )}
        </Card>
      )}

      <Card title="Thông tin thực tập">
        {uploadRow}
        {FIELDS.map((f) => (
          <Field key={f.key} required label={f.label} hint={confirmations[f.key] === "ai_confirmed" ? (pulseSave ? "AI điền từ giấy: kiểm tra rồi bấm Lưu bản nháp" : "Giá trị do AI gợi ý, bạn đã xác nhận") : undefined}>
            {f.wide ? (
              <textarea value={form[f.key]} disabled={!canEdit(f.key)} onChange={(e) => set(f.key, e.target.value as never)} />
            ) : (
              <input type={f.type ?? "text"} value={form[f.key]} disabled={!canEdit(f.key)} onChange={(e) => set(f.key, e.target.value as never)} />
            )}
          </Field>
        ))}
        <Field required label="Hình thức thực tập">
          <select value={form.mode} disabled={!canEdit("mode")} onChange={(e) => set("mode", e.target.value as Form["mode"])}>
            {Object.entries(MODE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <ErrorToast title="Không lưu được bản nháp" message={save.error} />
        <OkText message={message} />
        {personalOnly && (
          <>
            <ErrorToast title="Không lưu được thông tin cá nhân" message={personal.error} />
            <Row>
              <Button
                variant="primary"
                disabled={personal.busy || !form.position.trim() || !form.job_description.trim()}
                onClick={() =>
                  void personal.run(async () => {
                    await send("PUT", "/api/student/internship/personal", { position: form.position, job_description: form.job_description, mode: form.mode });
                    setMessage("Đã lưu thông tin cá nhân.");
                  })
                }
              >
                Lưu thông tin cá nhân
              </Button>
            </Row>
          </>
        )}
        {editable && (
          <div ref={saveRef}>
            <Row>
              <Button disabled={save.busy} className={pulseSave ? PULSE : undefined} onClick={() => void saveDraft()}>
                Lưu bản nháp
              </Button>
            </Row>
          </div>
        )}
      </Card>

      {(row || editable) && (
        <Card title="Giấy tiếp nhận của doanh nghiệp">
          {uploadRow}
          <div className="mt-3 border-t border-foreground/15 pt-3">
            {RECEIPT_FIELDS.map((f) => (
              <Field key={f.key} required label={f.label} hint={confirmations[f.key] === "ai_confirmed" ? (pulseSave ? "AI điền từ giấy: kiểm tra rồi bấm Lưu bản nháp" : "Giá trị do AI gợi ý, bạn đã xác nhận") : undefined}>
                <input type={f.type ?? "text"} value={form[f.key]} disabled={!canEdit(f.key)} onChange={(e) => set(f.key, e.target.value as never)} />
              </Field>
            ))}
            {editable && (
              <Row>
                <Button disabled={save.busy} className={pulseSave ? PULSE : undefined} onClick={() => void saveDraft()}>
                  Lưu bản nháp
                </Button>
              </Row>
            )}
          </div>
          <EvidencePreviewDialog
            title="Xem lại giấy tiếp nhận"
            file={previewFile}
            busy={docs.busy}
            onCancel={() => setPreviewFile(null)}
            onConfirm={() => {
              const file = previewFile;
              if (!file) return;
              void uploadDoc(file).then(() => setPreviewFile(null));
            }}
          />
          {extract.busy && <p className="text-sm text-muted-foreground">AI đang đọc giấy...</p>}
          <ErrorToast title="Không tải được giấy tiếp nhận" message={docs.error} />
          <ErrorToast title="Không đọc được thông tin từ giấy tiếp nhận" message={extract.error} />
          {note && <p>{note}</p>}
          {warnings.map((w) => (
            <p key={w} className="text-sm font-medium text-red-600" role="alert">
              {w}
            </p>
          ))}
          {suggestions && Object.keys(suggestions).length > 0 && (
            <>
              <p>
                <strong>Gợi ý của AI</strong> — chỉ là gợi ý, hãy kiểm tra và xác nhận từng trường:{" "}
                <Button onClick={() => accept(suggestions)}>Dùng tất cả</Button>
              </p>
              {Object.entries(suggestions).map(([key, s]) => (
                <Row key={key}>
                  <span>
                    {ALL_FIELDS.find((f) => f.key === key)?.label ?? (key === "mode" ? "Hình thức thực tập" : key)}: <strong>{key === "mode" ? (MODE_LABEL[s.value as Form["mode"]] ?? s.value) : s.value}</strong>
                  </span>
                  <Badge tone={s.confidence >= 0.8 ? "good" : "warn"}>Tin cậy {Math.round(s.confidence * 100)}%</Badge>
                  {s.source && <span>Nguồn: “{s.source}”</span>}
                  <Button onClick={() => accept({ [key]: s })}>Xác nhận và dùng</Button>
                </Row>
              ))}
            </>
          )}
        </Card>
      )}

      {row && editable && (
        <Card title="Kiểm tra trước khi nộp">
          {dirty && (
            <div className="mb-3">
              <NoticeCard tone="warning" title="Có thay đổi chưa lưu">
                <p className="m-0">Kết quả bên dưới là của bản đã lưu, chưa tính các ô vừa điền hoặc sửa. Lưu bản nháp để kiểm tra lại.</p>
                <div className="mt-2">
                  <Button variant="primary" disabled={save.busy} onClick={() => void saveDraft()}>
                    {save.busy ? "Đang lưu..." : "Lưu và kiểm tra lại"}
                  </Button>
                </div>
              </NoticeCard>
            </div>
          )}
          {checks.length === 0 && <Empty>Lưu bản nháp để xem kết quả kiểm tra.</Empty>}
          {checks.length > 0 && problems.length === 0 && !dirty && (
            <p className="m-0 flex items-center gap-2 text-sm font-medium text-green-700">
              <CheckCircle2 aria-hidden className="size-4" /> Không có mục nào cần sửa, có thể nộp hồ sơ.
            </p>
          )}
          {problems.map((c) => (
            <div key={c.code} className={dirty ? "opacity-50" : undefined}>
              <Row>
                <Badge tone={c.level === "error" ? "bad" : "warn"}>{c.level === "error" ? "Lỗi" : "Lưu ý"}</Badge>
                <span>
                  {c.label}
                  {c.detail && ` — ${c.detail}`}
                </span>
              </Row>
              {c.citation && (
                <blockquote>
                  {c.citation.doc_title} ({c.citation.version}), Điều {c.citation.article_no}
                  {c.citation.clause_no ? `, khoản ${c.citation.clause_no}` : ""}: {c.citation.text}
                  {c.citation.is_sample && " (văn bản mẫu)"}
                </blockquote>
              )}
            </div>
          ))}
        </Card>
      )}

      {row && editable && (
        <div>
          <ErrorToast title="Không nộp được hồ sơ" message={submit.error} />
          <Button disabled={submit.busy || save.busy || dirty || blocking.length > 0 || missing.length > 0} onClick={() => void submitIt()}>
            Nộp hồ sơ cho giảng viên
          </Button>
          {missing.length > 0 && <p className="mb-0 mt-2 text-sm text-muted-foreground">Còn {missing.length} ô bắt buộc chưa điền.</p>}
        </div>
      )}
    </>
  );
}
