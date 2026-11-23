"use client";

import { useEffect, useRef, useState } from "react";
import { FIELD_LABEL, PULSE, type PendingAutofill, type Suggestion } from "@/lib/autofill";
import { send } from "@/lib/http";
import { useAction } from "@/lib/hooks";
import type { Evidence, EvidenceMismatch } from "@/lib/types";
import { Badge, Button, ErrorText, OkText, Row } from "@/components/ui/ui";

// Trường của giấy xác nhận / phiếu đánh giá (khớp COMPLETION_FIELDS ở BE và agent).
const FIELDS: { key: string; type?: string; wide?: boolean }[] = [
  { key: "company_name" },
  { key: "company_tax_code" },
  { key: "student_name" },
  { key: "student_code" },
  { key: "position" },
  { key: "department" },
  { key: "actual_start_date", type: "date" },
  { key: "actual_end_date", type: "date" },
  { key: "mentor_name" },
  { key: "result_grade" },
  { key: "score" },
  { key: "signer_name" },
  { key: "signer_title" },
  { key: "letter_number" },
  { key: "letter_date", type: "date" },
  { key: "has_stamp" },
  { key: "company_comment", wide: true },
];
const READABLE = ["application/pdf", "image/png", "image/jpeg"];

// Thông tin trên giấy xác nhận (M5): AI đọc → điền sẵn (chưa lưu) → SV kiểm, sửa → "Xác nhận thông tin" → BE đối chiếu với hồ sơ.
export default function EvidenceFieldsForm({
  evidence,
  editable,
  autofill,
  autoExtract,
  onSaved,
}: {
  evidence: Evidence;
  editable: boolean;
  autofill: PendingAutofill | null;
  // Vừa tải giấy và SV chọn "Có, tự điền": gọi AI ngay khi mở.
  autoExtract?: boolean;
  onSaved: () => void;
}) {
  const saved = evidence.extraction;
  const [values, setValues] = useState<Record<string, string>>(() => ({ ...(saved?.fields ?? {}), ...toValues(autofill?.fields) }));
  const [marks, setMarks] = useState<Record<string, string>>(() => ({ ...(saved?.confirmations ?? {}), ...toMarks(autofill?.fields) }));
  const [confidence, setConfidence] = useState<Record<string, Suggestion>>(autofill?.fields ?? {});
  const [mismatches, setMismatches] = useState<EvidenceMismatch[]>(saved?.mismatches ?? []);
  const [pulse, setPulse] = useState(Boolean(autofill));
  const [open, setOpen] = useState(Boolean(autofill || autoExtract || saved));
  const [message, setMessage] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const extract = useAction();
  const confirm = useAction();
  const confirmRef = useRef<HTMLDivElement>(null);

  async function runExtract() {
    await extract.run(async () => {
      const result = await send<{ fields: Record<string, Suggestion>; notes: string }>("POST", `/api/student/evidence/${evidence.id}/extract`);
      setValues((v) => ({ ...v, ...toValues(result.fields) }));
      setMarks((m) => ({ ...m, ...toMarks(result.fields) }));
      setConfidence(result.fields);
      setNote(result.notes || (Object.keys(result.fields).length === 0 ? "AI không đọc được trường nào; hãy nhập tay." : null));
      if (Object.keys(result.fields).length > 0) setPulse(true);
    });
  }

  useEffect(() => {
    if (autoExtract && editable) void runExtract();
    if (autofill) confirmRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    // chỉ khi vừa mở
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save() {
    setMessage(null);
    setPulse(false);
    const ok = await confirm.run(async () => {
      const result = await send<{ mismatches: EvidenceMismatch[] }>("PUT", `/api/student/evidence/${evidence.id}/fields`, { fields: values, confirmations: marks });
      setMismatches(result.mismatches);
    });
    if (ok) {
      setMessage("Đã xác nhận thông tin trên giấy.");
      onSaved();
    }
  }

  if (!open) {
    return editable && READABLE.includes(evidence.mime) ? (
      <Button
        onClick={() => {
          setOpen(true);
          void runExtract();
        }}
        disabled={extract.busy}
      >
        AI đọc giấy và điền thông tin
      </Button>
    ) : null;
  }

  return (
    <div className="mt-2 rounded-lg border-2 border-beige-strong bg-background p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <strong className="text-sm">Thông tin trên giấy</strong>
        {editable && READABLE.includes(evidence.mime) && (
          <Button onClick={() => void runExtract()} disabled={extract.busy}>
            {extract.busy ? "AI đang đọc giấy..." : "AI đọc lại giấy"}
          </Button>
        )}
      </div>
      {note && <p className="m-0 mb-2 text-sm text-muted-foreground">{note}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {FIELDS.map((f) => {
          const s = confidence[f.key];
          return (
            <label key={f.key} className={f.wide ? "sm:col-span-2" : undefined}>
              <span className="flex items-center gap-2 text-xs text-muted-foreground">
                {FIELD_LABEL[f.key] ?? f.key}
                {s && <Badge tone={s.confidence >= 0.8 ? "good" : "warn"}>AI {Math.round(s.confidence * 100)}%</Badge>}
              </span>
              {f.wide ? (
                <textarea value={values[f.key] ?? ""} disabled={!editable} onChange={(e) => edit(f.key, e.target.value)} rows={3} />
              ) : (
                <input type={f.type ?? "text"} value={f.type === "date" ? (values[f.key] ?? "").slice(0, 10) : (values[f.key] ?? "")} disabled={!editable} onChange={(e) => edit(f.key, e.target.value)} />
              )}
              {s?.source && <small className="block truncate text-muted-foreground" title={s.source}>Nguồn: “{s.source}”</small>}
            </label>
          );
        })}
      </div>
      {mismatches.length > 0 && (
        <div className="mt-3 space-y-1" role="alert">
          {mismatches.map((m) => (
            <p key={m.field + m.label} className="m-0 text-sm text-red-600">
              <strong>{m.label}</strong> — {m.detail}
            </p>
          ))}
          <p className="m-0 text-xs text-muted-foreground">Giảng viên sẽ thấy các cảnh báo này khi duyệt mốc.</p>
        </div>
      )}
      <ErrorText message={extract.error ?? confirm.error} />
      <OkText message={message} />
      {editable && (
        <div ref={confirmRef} className="mt-3">
          <Row>
            <Button variant="primary" className={pulse ? PULSE : undefined} disabled={confirm.busy} onClick={() => void save()}>
              Xác nhận thông tin
            </Button>
            {pulse && <span className="text-sm text-muted-foreground">AI đã điền từ giấy: kiểm tra rồi bấm xác nhận.</span>}
          </Row>
        </div>
      )}
    </div>
  );

  function edit(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
    setMarks((m) => ({ ...m, [key]: "manual" }));
  }
}

function toValues(fields: Record<string, Suggestion> | undefined): Record<string, string> {
  return Object.fromEntries(Object.entries(fields ?? {}).map(([k, s]) => [k, s.value]));
}

function toMarks(fields: Record<string, Suggestion> | undefined): Record<string, string> {
  return Object.fromEntries(Object.keys(fields ?? {}).map((k) => [k, "ai_confirmed"]));
}
