"use client";

import { useState } from "react";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { MODE_LABEL, fmtDate } from "@/lib/labels";
import type { Check, InternshipDetail } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, FilePicker, OkText, Page, Row, StatusBadge } from "@/components/ui/ui";
import DownloadDoc from "./DownloadDoc";

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
};

type Suggestion = { value: string; confidence: number; source: string };

const FIELDS: { key: keyof Form; label: string; type?: string; wide?: boolean }[] = [
  { key: "company_name", label: "Tên doanh nghiệp" },
  { key: "company_tax_code", label: "Mã số thuế (10 hoặc 13 số)" },
  { key: "company_address", label: "Địa chỉ doanh nghiệp" },
  { key: "position", label: "Vị trí thực tập" },
  { key: "mentor_name", label: "Người hướng dẫn tại doanh nghiệp" },
  { key: "mentor_email", label: "Email người hướng dẫn", type: "email" },
  { key: "mentor_phone", label: "Số điện thoại người hướng dẫn" },
  { key: "start_date", label: "Ngày bắt đầu", type: "date" },
  { key: "end_date", label: "Ngày kết thúc", type: "date" },
  { key: "job_description", label: "Mô tả công việc", wide: true },
];

const EDITABLE = ["draft", "revision_requested"];

export default function InternshipForm() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Hồ sơ thực tập">
      <Async state={state}>{(d) => <Editor key={d.internship?.version ?? 0} detail={d} reload={state.reload} />}</Async>
    </Page>
  );
}

function Editor({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const row = detail.internship;
  const [form, setForm] = useState<Form>({
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
  });
  const [confirmations, setConfirmations] = useState<Record<string, string>>({});
  const [suggestions, setSuggestions] = useState<Record<string, Suggestion> | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [checks, setChecks] = useState<Check[]>(detail.checks ?? []);
  const [message, setMessage] = useState<string | null>(null);
  const save = useAction();
  const submit = useAction(reload);
  const docs = useAction(reload);
  const extract = useAction();

  const editable = !row || EDITABLE.includes(row.status);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setConfirmations((c) => ({ ...c, [key]: "manual" }));
  }

  function payload() {
    return {
      ...form,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      confirmations,
    };
  }

  async function saveDraft() {
    setMessage(null);
    const ok = await save.run(async () => {
      const result = await send<{ checks: Check[] }>("PUT", "/api/student/internship", payload());
      setChecks(result.checks);
    });
    if (ok) {
      setMessage("Đã lưu bản nháp.");
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
      const result = await send<{ fields: Record<string, Suggestion>; notes: string }>("POST", `/api/student/internship/documents/${documentId}/extract`);
      setSuggestions(result.fields);
      setNote(result.notes || null);
    });
  }

  function accept(key: string, s: Suggestion) {
    setForm((f) => ({ ...f, [key]: s.value }));
    setConfirmations((c) => ({ ...c, [key]: "ai_confirmed" }));
    setSuggestions((all) => {
      if (!all) return all;
      const rest = { ...all };
      delete rest[key];
      return rest;
    });
  }

  const blocking = checks.filter((c) => !c.ok && c.level === "error");

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
          {!editable && <p>Hồ sơ đã nộp nên không sửa tại chỗ. Nếu giảng viên yêu cầu sửa, bạn sẽ chỉnh và nộp lại.</p>}
        </Card>
      )}

      <Card title="Thông tin thực tập">
        {FIELDS.map((f) => (
          <Field key={f.key} label={f.label} hint={confirmations[f.key] === "ai_confirmed" ? "Giá trị do AI gợi ý, bạn đã xác nhận" : undefined}>
            {f.wide ? (
              <textarea value={form[f.key]} disabled={!editable} onChange={(e) => set(f.key, e.target.value as never)} />
            ) : (
              <input type={f.type ?? "text"} value={form[f.key]} disabled={!editable} onChange={(e) => set(f.key, e.target.value as never)} />
            )}
          </Field>
        ))}
        <Field label="Hình thức thực tập">
          <select value={form.mode} disabled={!editable} onChange={(e) => set("mode", e.target.value as Form["mode"])}>
            {Object.entries(MODE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <ErrorText message={save.error} />
        <OkText message={message} />
        {editable && (
          <Row>
            <Button disabled={save.busy} onClick={() => void saveDraft()}>
              Lưu bản nháp
            </Button>
          </Row>
        )}
      </Card>

      {row && (
        <Card title="Giấy tiếp nhận của doanh nghiệp">
          {detail.documents.length === 0 && <Empty>Chưa tải giấy tiếp nhận (PDF, PNG hoặc JPG).</Empty>}
          {detail.documents.map((doc) => (
            <Row key={doc.id}>
              <DownloadDoc href={`/api/documents/${doc.id}/download`} name={doc.filename} />
              <span>({fmtDate(doc.uploaded_at)})</span>
              {editable && (
                <Button disabled={extract.busy} onClick={() => void runExtract(doc.id)}>
                  AI gợi ý các trường
                </Button>
              )}
            </Row>
          ))}
          {editable && <FilePicker label="Tải giấy tiếp nhận" accept=".pdf,.png,.jpg,.jpeg" disabled={docs.busy} onFile={(file) => void docs.run(() => upload("/api/student/internship/documents", file))} />}
          <ErrorText message={docs.error ?? extract.error} />
          {note && <p>{note}</p>}
          {suggestions && Object.keys(suggestions).length > 0 && (
            <>
              <p>
                <strong>Gợi ý của AI</strong> — chỉ là gợi ý, hãy kiểm tra và xác nhận từng trường:
              </p>
              {Object.entries(suggestions).map(([key, s]) => (
                <Row key={key}>
                  <span>
                    {FIELDS.find((f) => f.key === key)?.label ?? key}: <strong>{s.value}</strong>
                  </span>
                  <Badge tone={s.confidence >= 0.8 ? "good" : "warn"}>Tin cậy {Math.round(s.confidence * 100)}%</Badge>
                  {s.source && <span>Nguồn: “{s.source}”</span>}
                  <Button onClick={() => accept(key, s)}>Xác nhận và dùng</Button>
                </Row>
              ))}
            </>
          )}
        </Card>
      )}

      {row && editable && (
        <Card title="Kiểm tra trước khi nộp">
          {checks.length === 0 && <Empty>Lưu bản nháp để xem kết quả kiểm tra.</Empty>}
          {checks.map((c) => (
            <div key={c.code}>
              <Row>
                <Badge tone={c.ok ? "good" : c.level === "error" ? "bad" : "warn"}>{c.ok ? "Đạt" : c.level === "error" ? "Lỗi" : "Lưu ý"}</Badge>
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
          <ErrorText message={submit.error} />
          <Button variant="primary" disabled={submit.busy || save.busy || blocking.length > 0} onClick={() => void submitIt()}>
            Nộp hồ sơ cho giảng viên
          </Button>
        </Card>
      )}
    </>
  );
}
