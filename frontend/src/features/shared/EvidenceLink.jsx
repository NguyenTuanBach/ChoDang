import { useState } from "react";
import { EvidencePreview } from "./EvidencePreview";

// Nút xem file minh chứng: mở cửa sổ xem trực tiếp (PDF/ảnh/Word), trong đó có nút tải về.

export function EvidenceLink({ id, children }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="link-btn" style={{ marginRight: 12 }} onClick={() => setOpen(true)}>{children}</button>
      {open && <EvidencePreview id={id} onClose={() => setOpen(false)} />}
    </>
  );
}
