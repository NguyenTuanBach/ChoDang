import { useState } from "react";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { Button } from "../../components/ui";

/** Ô nhận xét + 2 nút Chấp nhận / Trả lại dùng chung cho mốc và nhật ký (chi tiết hồ sơ + hàng chờ). */
export default function ReviewInline({ path, rejectDecision, onDone, accepted = "accepted" }) {
  const { run } = useToast();
  const [comment, setComment] = useState("");
  const send = async (decision) => {
    try {
      await run(() => api("POST", path, { decision, comment }), "Đã cập nhật");
    } catch {
      return; // run() đã hiện lỗi trên toast; không tải lại và không để lỗi lọt ra ngoài
    }
    onDone();
  };
  return (
    <div className="row" style={{ marginTop: 8 }}>
      <input className="input" style={{ flex: 1, minWidth: 180 }} placeholder="Nhận xét (bắt buộc khi trả lại)" aria-label="Nhận xét" value={comment} onChange={(e) => setComment(e.target.value)} />
      <Button size="sm" variant="ok" onClick={() => send(accepted)}>Chấp nhận</Button>
      <Button size="sm" variant="danger" onClick={() => send(rejectDecision)}>Trả lại</Button>
    </div>
  );
}
