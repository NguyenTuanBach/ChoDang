import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useChat } from "../../context/ChatContext";
import { Button, PageHead } from "../../components/ui";
import Icon from "../../components/ui/Icon";

// Trợ lý AI hỏi đáp quy định (dùng chung mọi vai trò). Hội thoại giữ trong ChatContext.

const SUGGESTIONS = [
  "Thời gian thực tập tối thiểu là bao nhiêu tuần?",
  "Khi nào phải nộp đề cương?",
  "Em có được gia hạn nộp báo cáo không?",
  "Mỗi tuần cần bao nhiêu giờ?",
];

export default function Assistant() {
  const { messages, busy, ask } = useChat();
  const [q, setQ] = useState("");
  const chatRef = useRef();
  // Chỉ cuộn khung chat tới tin mới nhất — scrollIntoView sẽ kéo cả trang và đẩy ô nhập ra khỏi màn hình
  useEffect(() => { const el = chatRef.current; if (el) el.scrollTop = el.scrollHeight; }, [messages]);

  const send = (text) => {
    const question = text.trim();
    if (!question || busy) return;
    setQ("");
    ask(question);
  };

  return (
    <div className="assistant">
      <PageHead title="Trợ lý chính sách thực tập"
        subtitle="Trợ lý chỉ trả lời theo văn bản quy định đang có hiệu lực và luôn dẫn nguồn. Trợ lý không duyệt hay cam kết kết quả — mọi quyết định do giảng viên đưa ra." />
      <div className="chat" aria-live="polite" ref={chatRef}>
        {messages.length === 0 && <p className="muted chat__empty">Hãy đặt câu hỏi về thủ tục, thời hạn hay quy định thực tập.</p>}
        {messages.map((m, idx) => <Message key={idx} m={m} />)}
      </div>
      <div className="composer">
        <div className="suggest">
          {SUGGESTIONS.map((s) => <button key={s} className="chip" disabled={busy} onClick={() => send(s)}>{s}</button>)}
        </div>
        <form className="ask" onSubmit={(e) => { e.preventDefault(); send(q); }}>
          <label className="sr-only" htmlFor="q">Câu hỏi</label>
          <input id="q" value={q} onChange={(e) => setQ(e.target.value)} maxLength={2000} placeholder="Hỏi về thủ tục, thời hạn hay quy định thực tập…" />
          <Button variant="primary" type="submit" disabled={busy || !q.trim()} style={{ minHeight: 52 }}>Hỏi</Button>
        </form>
      </div>
    </div>
  );
}

const NO_LLM = { smalltalk: "lời chào", refused: "bị guardrail chặn", not_found: "không có đoạn quy định phù hợp" };
const sec = (ms) => (ms / 1000).toFixed(1) + "s";

/** Dòng minh bạch dưới câu trả lời: có gọi LLM thật không, mất bao lâu. */
export function TimingLine({ m }) {
  const t = m.timing;
  if (!t) return null;
  return (
    <div className="small muted msg__timing" aria-label="Thông tin xử lý">
      {t.llm_called
        ? `Đã gọi ${t.model} · LLM ${sec(t.llm_ms)} · tổng ${sec(t.total_ms ?? 0)}`
        : `Không gọi LLM (${NO_LLM[m.outcome] ?? "trả lời trực tiếp"}) · tổng ${sec(t.total_ms ?? 0)}`}
    </div>
  );
}

function Message({ m }) {
  if (m.role === "user") {
    return <div className="msg msg--user"><div className="msg__bubble">{m.content}</div></div>;
  }
  return (
    <div className="msg">
      <div className="msg__ai"><Icon name="sparkle" size={18} /></div>
      <div>
        <div className="msg__bubble">
          {m.status && <span className="muted small">{m.status} </span>}
          {m.content}
          {m.mode?.startsWith("extractive") && <div className="small muted" style={{ marginTop: 6 }}>Trích nguyên văn quy định (không diễn giải).</div>}
        </div>
        <TimingLine m={m} />
        {m.citations?.length > 0 && (
          <div className="cites">
            <b className="muted">Nguồn</b>
            {m.citations.map((c) => (
              <details key={c.n}><summary>[{c.n}] {c.label}</summary><div className="pre">{c.excerpt}</div></details>
            ))}
          </div>
        )}
        {m.suggest && <p style={{ marginTop: 8 }}><Link to="/">→ Mở mục Mốc để tạo yêu cầu gia hạn</Link></p>}
      </div>
    </div>
  );
}
