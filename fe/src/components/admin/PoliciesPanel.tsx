"use client";

import { useState } from "react";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate } from "@/lib/labels";
import type { PolicyEmbedResult, PolicyExtractResult, PolicyIngestResult, PolicyPreview, PolicyVersion } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, OkText, Page, Row, Table, type Tone } from "@/components/ui/ui";

const STATUS: Record<PolicyVersion["status"], { label: string; tone: Tone }> = {
  draft: { label: "Bản nháp", tone: "warn" },
  published: { label: "Đang hiệu lực", tone: "good" },
  superseded: { label: "Đã thay thế", tone: "neutral" },
};

// Quản trị văn bản quy định: nạp → xem trước các đoạn đã tách → xuất bản (QTV xác nhận, HITL).
export default function PoliciesPanel() {
  const state = useApi<PolicyVersion[]>("/api/admin/policies");
  const [previewId, setPreviewId] = useState<string | null>(null);
  return (
    <Page title="Văn bản quy định">
      <Card title="Các phiên bản" className="bg-background">
        <Async state={state}>
          {(list) =>
            list.length === 0 ? (
              <Empty>Chưa có văn bản nào.</Empty>
            ) : (
              <Table head={["Mã", "Tên", "Phiên bản", "Hiệu lực từ", "Hiệu lực đến", "Đoạn", "Embedding", "Trạng thái", ""]}>
                {list.map((v) => (
                  <VersionRow key={v.id} version={v} reload={state.reload} onPreview={() => setPreviewId(v.id)} />
                ))}
              </Table>
            )
          }
        </Async>
      </Card>
      {previewId && <Preview id={previewId} onClose={() => setPreviewId(null)} />}
      <IngestForm
        onIngested={(id) => {
          state.reload();
          setPreviewId(id);
        }}
      />
    </Page>
  );
}

function VersionRow({ version: v, reload, onPreview }: { version: PolicyVersion; reload: () => void; onPreview: () => void }) {
  const publish = useAction(reload);
  const embed = useAction(reload);
  const [embedNote, setEmbedNote] = useState<string | null>(null);
  const s = STATUS[v.status];
  const missing = v.chunk_count - v.embedded_count;

  async function runEmbed() {
    setEmbedNote(null);
    let result: PolicyEmbedResult | undefined;
    await embed.run(async () => {
      result = await send<PolicyEmbedResult>("POST", `/api/admin/policies/versions/${v.id}/embed`);
    });
    if (!result) return;
    const left = result.version.chunk_count - result.version.embedded_count;
    if (!result.agent_enabled) setEmbedNote("BE chưa cấu hình agent (AGENT_API_URL): chưa tạo được embedding.");
    else if (left > 0) setEmbedNote(`Mới tạo ${result.embedded_now} đoạn, còn thiếu ${left} (agent không chạy hoặc lỗi LLM). Thử lại sau.`);
  }
  return (
    <tr>
      <td>{v.doc_code}</td>
      <td>
        {v.doc_title} {v.is_sample && <Badge tone="warn">Bản mẫu</Badge>}
      </td>
      <td>{v.version_label}</td>
      <td className="whitespace-nowrap">{fmtDate(v.effective_from)}</td>
      <td className="whitespace-nowrap">{v.effective_to ? fmtDate(v.effective_to) : "—"}</td>
      <td>{v.chunk_count}</td>
      <td className="whitespace-nowrap">
        {missing <= 0 ? (
          <Badge tone="good">Đủ</Badge>
        ) : (
          <span title="Đoạn chưa có embedding chỉ tìm được bằng từ khóa">
            <Badge tone="warn">
              {v.embedded_count}/{v.chunk_count}
            </Badge>
          </span>
        )}
      </td>
      <td>
        <Badge tone={s.tone}>{s.label}</Badge>
      </td>
      <td>
        <Row>
          <Button onClick={onPreview}>Xem</Button>
          {missing > 0 && (
            <Button disabled={embed.busy} onClick={() => void runEmbed()}>
              {embed.busy ? "Đang tạo..." : "Tạo embedding"}
            </Button>
          )}
          {v.status === "draft" && (
            <Button
              variant="primary"
              disabled={publish.busy}
              onClick={() => {
                if (window.confirm(`Xuất bản ${v.doc_code} ${v.version_label}? Bản đang hiệu lực của văn bản này sẽ bị đóng.`)) {
                  void publish.run(() => send("POST", `/api/admin/policies/versions/${v.id}/publish`));
                }
              }}
            >
              Xuất bản
            </Button>
          )}
        </Row>
        <ErrorText message={publish.error ?? embed.error} />
        {embedNote && <p className="text-sm text-muted-foreground">{embedNote}</p>}
      </td>
    </tr>
  );
}

function Preview({ id, onClose }: { id: string; onClose: () => void }) {
  const state = useApi<PolicyPreview>(`/api/admin/policies/versions/${id}`);
  return (
    <Card title="Xem trước các đoạn đã tách" className="bg-background">
      <Async state={state}>
        {({ version, chunks }) => (
          <>
            <p>
              <strong>{version.doc_code}</strong> {version.version_label} — {chunks.length} đoạn. Kiểm tra Điều/Khoản đã tách đúng trước khi xuất bản.
            </p>
            <Table head={["Điều", "Khoản", "Tiêu đề", "Nội dung"]}>
              {chunks.map((c) => (
                <tr key={c.chunk_id}>
                  <td>{c.article_no}</td>
                  <td>{c.clause_no ?? "—"}</td>
                  <td>{c.heading}</td>
                  <td>{c.text}</td>
                </tr>
              ))}
            </Table>
          </>
        )}
      </Async>
      <Button onClick={onClose}>Đóng</Button>
    </Card>
  );
}

function IngestForm({ onIngested }: { onIngested: (versionId: string) => void }) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [issuer, setIssuer] = useState("");
  const [label, setLabel] = useState("v1");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sample, setSample] = useState(false);
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [fileNote, setFileNote] = useState<string | null>(null);
  const action = useAction();
  const reading = useAction();

  async function readFile(file: File | undefined) {
    if (!file) return;
    setFileNote(null);
    let result: PolicyExtractResult | undefined;
    await reading.run(async () => {
      result = await upload<PolicyExtractResult>("/api/admin/policies/extract", file);
    });
    if (!result) return;
    setText(result.text);
    if (!title.trim()) setTitle(file.name.replace(/\.[^.]+$/, ""));
    setFileNote(
      result.warning
        ? `Đã đọc ${result.text.length.toLocaleString("vi-VN")} ký tự từ ${result.filename}, nhưng chưa tách được Điều/Khoản: ${result.warning}. Hãy sửa nội dung bên dưới (mỗi điều bắt đầu bằng "Điều N.").`
        : `Đã đọc ${result.filename}: tách thử được ${result.chunk_count} đoạn. Kiểm tra nội dung bên dưới rồi bấm "Nạp và tách đoạn".`,
    );
  }

  const ready = code.trim() && title.trim() && label.trim() && from && text.trim();

  async function submit() {
    setNote(null);
    let result: PolicyIngestResult | undefined;
    const ok = await action.run(async () => {
      result = await send<PolicyIngestResult>("POST", "/api/admin/policies", {
        code: code.trim(),
        title: title.trim(),
        issuer: issuer.trim(),
        version_label: label.trim(),
        effective_from: from,
        effective_to: to || null,
        is_sample: sample,
        text,
      });
    });
    if (ok && result) {
      const embedding = result.embedded_count < result.chunk_count ? " Chưa có embedding (chỉ tìm được bằng từ khóa): bấm \"Tạo embedding\" ở bảng khi agent chạy." : "";
      setNote(`Đã tạo bản nháp: ${result.chunk_count} đoạn.${embedding}`);
      setText("");
      onIngested(result.version.id);
    }
  }

  return (
    <Card title="Nạp văn bản mới" className="bg-background">
      <Row>
        <Field label="Mã văn bản">
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="QD-TT-01" />
        </Field>
        <Field label="Phiên bản">
          <input value={label} onChange={(e) => setLabel(e.target.value)} size={8} />
        </Field>
        <Field label="Hiệu lực từ">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <Field label="Đến (nếu có)">
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
      </Row>
      <Row>
        <Field label="Tên văn bản">
          <input value={title} onChange={(e) => setTitle(e.target.value)} size={50} />
        </Field>
        <Field label="Cơ quan ban hành">
          <input value={issuer} onChange={(e) => setIssuer(e.target.value)} size={30} />
        </Field>
      </Row>
      <label>
        <input type="checkbox" checked={sample} onChange={(e) => setSample(e.target.checked)} /> Bản mẫu (không phải quy chế thật)
      </label>
      <Field label="Tải tệp quy chế (.md, .txt, .docx, .pdf có lớp chữ; tối đa 10 MB)">
        <input
          type="file"
          accept=".md,.markdown,.txt,.docx,.pdf,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={reading.busy}
          onChange={(e) => {
            void readFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </Field>
      {reading.busy && <p>Đang đọc tệp...</p>}
      <ErrorText message={reading.error} />
      {fileNote && <p className="text-sm text-muted-foreground">{fileNote}</p>}
      <Field label="Nội dung (đọc từ tệp hoặc dán vào)">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={12} />
      </Field>
      <Button variant="primary" disabled={action.busy || !ready} onClick={() => void submit()}>
        {action.busy ? "Đang nạp..." : "Nạp và tách đoạn"}
      </Button>
      <ErrorText message={action.error} />
      <OkText message={note} />
    </Card>
  );
}
