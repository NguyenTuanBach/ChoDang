"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAssistant, type AssistantApi, type AssistantOptions } from "@/lib/assistant/useAssistant";
import { currentPageRef, pageHref } from "@/lib/nav";
import { useCurrentUser } from "@/lib/user-context";

const OPEN_KEY = "vin15.assistant.open";

export interface AssistantContextValue {
  assistant: AssistantApi;
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  // Mở ngăn rồi gửi câu hỏi (dùng cho câu hỏi gợi ý ở trang khác).
  askInDock: (question: string) => void;
}

const AssistantContext = createContext<AssistantContextValue | null>(null);

export function useAssistantContext(): AssistantContextValue {
  const value = useContext(AssistantContext);
  if (!value) throw new Error("useAssistantContext phải dùng bên trong <AssistantProvider>");
  return value;
}

function readOpen(): boolean {
  try {
    return window.localStorage.getItem(OPEN_KEY) === "1";
  } catch {
    return false;
  }
}

// Giữ MỘT phiên hội thoại (một WebSocket) cho cả khung ứng dụng: ngăn Trợ lý và trang /assistant dùng chung, chuyển trang không ngắt chat.
// Cũng là nơi thực thi hành động điều hướng mà trợ lý đề nghị: mỗi lượt chỉ một lần, chỉ với lượt đang chạy (lịch sử tải lại không có `actions`),
// và URL do FE tự suy ra từ khóa trang theo vai trò của người dùng (khóa lạ bị bỏ qua).
// Mỗi câu hỏi gửi kèm trang đang mở (khóa + mã hồ sơ, không gửi URL) để trợ lý hiểu "trang này".
export default function AssistantProvider({ children, options }: { children: ReactNode; options?: AssistantOptions }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useCurrentUser();
  const base = useAssistant(options);
  const pathRef = useRef(pathname);
  useEffect(() => {
    pathRef.current = pathname;
  }, [pathname]);
  const baseAsk = base.ask;
  const askWithPage = useCallback((question: string) => baseAsk(question, currentPageRef(user.role, pathRef.current ?? "")), [baseAsk, user.role]);
  const assistant = useMemo<AssistantApi>(() => ({ ...base, ask: askWithPage }), [base, askWithPage]);
  // Provider chỉ dựng sau khi đã biết người dùng (phía trình duyệt), nên đọc localStorage ngay khi khởi tạo là an toàn.
  const [open, setOpenState] = useState(readOpen);
  const executed = useRef(new Set<string>());

  const setOpen = useCallback((next: boolean) => {
    setOpenState(next);
    try {
      window.localStorage.setItem(OPEN_KEY, next ? "1" : "0");
    } catch {
      // không lưu được: chỉ mất việc nhớ trạng thái
    }
  }, []);
  const toggle = useCallback(() => setOpen(!open), [open, setOpen]);

  const { ask } = assistant;
  const askInDock = useCallback(
    (question: string) => {
      setOpen(true);
      void ask(question);
    },
    [ask, setOpen],
  );

  useEffect(() => {
    for (const turn of assistant.state.turns) {
      if (turn.phase !== "done" || turn.actions.length === 0 || executed.current.has(turn.turnId)) continue;
      executed.current.add(turn.turnId);
      for (const action of turn.actions) {
        if (action.type !== "navigate") continue;
        const target = pageHref(user.role, action.page, { internshipId: action.internship_id, filters: action.filters });
        if (target) router.push(target.href);
      }
    }
  }, [assistant.state.turns, user.role, router]);

  // Ctrl/Cmd + J bật/tắt ngăn Trợ lý.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "j") {
        event.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const value = useMemo(() => ({ assistant, open, setOpen, toggle, askInDock }), [assistant, open, setOpen, toggle, askInDock]);
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}
