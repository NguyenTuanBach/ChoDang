import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { AiBox, Button, Citation } from "../../components/ui";

// Xem minh chứng ngay trên web: PDF nhúng trình xem của trình duyệt, ảnh hiển thị trực tiếp,
// DOCX hiện phần chữ do máy chủ trích ra. Không cần tải file về máy.

const fmtSize = (n) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

export function EvidencePreview({ id, onClose }) {
  const { run } = useToast();
  const { me } = useAuth();
  const reviewer = me?.role === "lecturer" || me?.role === "admin";
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);
  const box = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    let alive = true;
    api("GET", `/evidence/${id}/preview`).then((d) => alive && setP(d), (e) => alive && setError(e));
    return () => { alive = false; };
  }, [id]);

  useEffect(() => {
    const prev = document.activeElement;
    const onKey = (e) => { if (e.key === "Escape") close.current(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    box.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus?.();
    };
  }, []);

  // Link ký chỉ sống vài phút → lấy link mới mỗi lần bấm tải
  const download = async () => {
    const { url } = await run(() => api("GET", `/evidence/${id}/url`));
    window.location.assign(url);
  };

  return (
    <div className="preview-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="preview" role="dialog" aria-modal="true" aria-label={p ? `Xem ${p.filename}` : "Xem minh chứng"} tabIndex={-1} ref={box}>
        <header className="preview__head">
          <div className="preview__title">
            <b>{p?.filename || "Đang tải…"}</b>
            {p && <span className="small muted">{fmtSize(p.size)}</span>}
          </div>
          <div className="row">
            {p?.kind === "pdf" && <a className="btn btn--sm" href={p.url} target="_blank" rel="noopener noreferrer">Mở tab mới</a>}
            {p && p.kind !== "missing" && <Button size="sm" onClick={download}>Tải về</Button>}
            <Button size="sm" variant="primary" onClick={onClose}>Đóng</Button>
          </div>
        </header>
        <div className="preview__main">
        <div className="preview__body">
          {error && <p className="preview__msg">{error.message}</p>}
          {!error && !p && <p className="preview__msg">Đang tải…</p>}
          {p?.kind === "pdf" && <iframe className="preview__frame" src={p.url} title={p.filename} />}
          {p?.kind === "image" && <img className="preview__img" src={p.url} alt={p.filename} />}
          {p?.kind === "text" && (
            <>
              <p className="small muted preview__note">
                Bản xem nhanh chỉ gồm phần chữ của file Word{p.truncated ? " (đã cắt bớt)" : ""}. Định dạng gốc: tải file về.
              </p>
              <pre className="preview__text">{p.text}</pre>
            </>
          )}
          {p?.kind === "none" && <p className="preview__msg">Định dạng này không xem trực tiếp được. Hãy tải file về để xem.</p>}
          {p?.kind === "broken" && (
            <p className="preview__msg">{p.problem || "File PDF bị hỏng"} nên không hiển thị được.<br />Hãy thử tải về, hoặc trả lại để sinh viên nộp file khác.</p>
          )}
          {p?.kind === "missing" && <p className="preview__msg">File không còn trên máy chủ. Hãy yêu cầu sinh viên nộp lại.</p>}
        </div>
        {reviewer && <EvidenceAi id={id} />}
        </div>
      </div>
    </div>
  );
}

/** Gợi ý AI đọc minh chứng (chỉ GV/QTV). Tải sau file để không làm chậm việc xem. */
function EvidenceAi({ id }) {
  const [r, setR] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let alive = true;
    api("GET", `/evidence/${id}/review`).then((d) => alive && setR(d), (e) => alive && setError(e));
    return () => { alive = false; };
  }, [id]);

  const none = error || r?.unavailable;
  return (
    <aside className="preview__ai" aria-label="Gợi ý AI đọc minh chứng">
      <details open>
        <summary>Gợi ý AI đọc minh chứng</summary>
        {!r && !error && <p className="small muted">AI đang đọc file…</p>}
        {none && <p className="small muted">Chưa có gợi ý AI cho file này. Bạn vẫn xem file và duyệt bình thường.</p>}
        {r && !none && (
          <AiBox label={r.label}>
            <p>{r.summary}</p>
            {r.warnings.length > 0 && (
              <ul className="ai-warnings">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            )}
            {r.checklist.length > 0 && (
              <>
                <p className="small" style={{ marginBottom: 4 }}><b>Checklist: {r.evidence_label}</b></p>
                <ul className="ai-checklist">
                  {r.checklist.map((c) => (
                    <li key={c.item} className={c.found ? "is-found" : "is-missing"}>
                      <span aria-hidden="true">{c.found ? "✓" : "?"}</span> {c.item}
                      <span className="sr-only">{c.found ? " — có" : " — chưa thấy"}</span>
                    </li>
                  ))}
                </ul>
                <div><Citation c={r.checklist_citation} /></div>
              </>
            )}
            {r.uncovered_outcomes.length > 0 && (
              <p className="small">Chuẩn đầu ra chưa thấy nhắc tới: {r.uncovered_outcomes.map((o) => o.code).join(", ")}</p>
            )}
            <p className="small muted">{r.limits}{r.used_ocr ? " Chữ được đọc bằng OCR nên có thể sai." : ""}</p>
          </AiBox>
        )}
      </details>
    </aside>
  );
}
