"use client";

// Hook WebSocket của trợ lý hỏi đáp.
// Luồng: POST /api/assistant/ws-ticket → mở WS → gửi `auth{ticket}` → chờ `ready` → gửi `ask`.
// Mất kết nối giữa lượt: nối lại có backoff, rồi tải lại hội thoại (BE chạy hết lượt và lưu `final`).
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { ClientFrame, ConversationSummary, CurrentPageRef, ServerFrame } from "@/lib/assistant-protocol";
import { AssistantError, getConversation, listConversations, requestWsTicket, resolveWsUrl } from "./client";
import { chatReducer, initialChatState, type ChatAction, type ChatState, type UiError } from "./reducer";

export interface AssistantOptions {
  wsUrl?: string;
  createSocket?: (url: string) => WebSocket;
  fetchImpl?: typeof fetch;
  newTurnId?: () => string;
  backoffMs?: number[]; // độ trễ giữa các lần nối lại; hết danh sách thì bỏ cuộc
  pollMs?: number; // chu kỳ hỏi lại lịch sử khi lượt bị ngắt
  pollAttempts?: number;
  pingMs?: number;
  handshakeMs?: number;
}

export interface AssistantApi {
  state: ChatState;
  conversations: ConversationSummary[];
  ask: (question: string, page?: CurrentPageRef | null) => Promise<void>;
  cancel: () => void;
  newConversation: () => void;
  openConversation: (id: string) => Promise<void>;
  reload: () => Promise<void>;
  dismissNotice: () => void;
}

const DEFAULT_BACKOFF = [1000, 2000, 4000, 8000, 16000];
const OPEN = 1;

function toUiError(error: unknown, fallback: UiError["code"] = "connection_failed"): UiError {
  if (error instanceof AssistantError) return { code: error.code, message: error.message };
  return { code: fallback, message: error instanceof Error ? error.message : String(error) };
}

export function useAssistant(options: AssistantOptions = {}): AssistantApi {
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  const [state, rawDispatch] = useReducer(chatReducer, initialChatState);
  const stateRef = useRef<ChatState>(initialChatState);
  // Giữ bản sao đồng bộ để các hàm bất đồng bộ đọc được trạng thái mới nhất ngay sau dispatch.
  const dispatch = useCallback((action: ChatAction) => {
    stateRef.current = chatReducer(stateRef.current, action);
    rawDispatch(action);
  }, []);

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef<Promise<WebSocket> | null>(null);
  const aliveRef = useRef(false);
  const generationRef = useRef(0); // tăng khi đổi hội thoại để hủy vòng hỏi lại cũ
  // Xử lý đóng kết nối được gán trong effect (nó dùng ensureSocket, còn ensureSocket lại dùng attachSocket).
  const handleCloseRef = useRef<(code: number) => Promise<void>>(async () => {});

  const fetchImpl = useCallback(() => optionsRef.current.fetchImpl ?? fetch, []);

  // Danh sách chỉ là phụ: bỏ qua lỗi.
  const refreshConversations = useCallback(() => {
    listConversations(fetchImpl())
      .then((list) => {
        if (aliveRef.current) setConversations(list);
      })
      .catch(() => {});
  }, [fetchImpl]);

  const loadConversation = useCallback(
    async (id: string): Promise<boolean> => {
      try {
        const detail = await getConversation(id, fetchImpl());
        if (!aliveRef.current) return false;
        dispatch({ type: "conversation_loaded", detail });
        return true;
      } catch (error) {
        if (aliveRef.current) dispatch({ type: "local_error", error: toUiError(error, "connection_failed") });
        return false;
      }
    },
    [dispatch, fetchImpl],
  );

  const sleep = useCallback(
    (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)),
    [],
  );

  // Lượt bị ngắt: BE vẫn chạy hết và lưu `final`, nên hỏi lại lịch sử cho tới khi có câu trả lời.
  const pollInterrupted = useCallback(
    async (conversationId: string) => {
      const generation = generationRef.current;
      const { pollMs = 3000, pollAttempts = 10 } = optionsRef.current;
      for (let attempt = 0; attempt < pollAttempts; attempt += 1) {
        const pending = stateRef.current.turns.some((turn) => turn.phase === "interrupted");
        if (!pending) return;
        await sleep(pollMs);
        if (!aliveRef.current || generation !== generationRef.current) return;
        await loadConversation(conversationId);
      }
    },
    [loadConversation, sleep],
  );

  const attachSocket = useCallback(
    (ws: WebSocket) => {
      let pingTimer: ReturnType<typeof setInterval> | undefined;
      const pingMs = optionsRef.current.pingMs ?? 25000;
      if (pingMs > 0) {
        pingTimer = setInterval(() => {
          if (ws.readyState === OPEN) ws.send(JSON.stringify({ type: "ping" } satisfies ClientFrame));
        }, pingMs);
      }
      ws.onmessage = (event) => {
        const frame = parseFrame(event.data);
        if (frame) dispatch({ type: "frame", frame });
      };
      ws.onclose = (event) => {
        if (pingTimer) clearInterval(pingTimer);
        if (socketRef.current !== ws) return;
        socketRef.current = null;
        if (!aliveRef.current) return;
        void handleCloseRef.current(event.code);
      };
    },
    [dispatch],
  );

  const openSocket = useCallback(async (): Promise<WebSocket> => {
    const opts = optionsRef.current;
    const ticket = await requestWsTicket(fetchImpl());
    const url = opts.wsUrl ?? resolveWsUrl();
    const ws = opts.createSocket ? opts.createSocket(url) : new WebSocket(url);

    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new AssistantError("connection_failed", "Hết thời gian chờ BE xác nhận kết nối"));
        ws.close();
      }, opts.handshakeMs ?? 10000);
      const fail = (error: AssistantError) => {
        clearTimeout(timer);
        reject(error);
      };
      ws.onopen = () => ws.send(JSON.stringify({ type: "auth", ticket } satisfies ClientFrame));
      ws.onmessage = (event) => {
        const frame = parseFrame(event.data);
        if (frame?.type === "ready") {
          clearTimeout(timer);
          resolve();
        } else if (frame?.type === "error") {
          fail(new AssistantError(frame.code === "rate_limited" ? "rate_limited" : "auth_failed", frame.message));
        }
      };
      ws.onerror = () => fail(new AssistantError("connection_failed", "Không mở được kết nối tới BE"));
      ws.onclose = (event) => {
        if (event.code === 4401) fail(new AssistantError("auth_failed", "Phiên không hợp lệ hoặc vé đã hết hạn"));
        else if (event.code === 4429) fail(new AssistantError("rate_limited", "Quá nhiều kết nối đồng thời, thử lại sau"));
        else fail(new AssistantError("connection_failed", "Kết nối bị đóng trước khi sẵn sàng"));
      };
    }).catch((error) => {
      ws.onclose = null;
      ws.onerror = null;
      ws.onmessage = null;
      try {
        ws.close();
      } catch {
        // đã đóng
      }
      throw error;
    });

    socketRef.current = ws;
    attachSocket(ws);
    return ws;
  }, [attachSocket, fetchImpl]);

  const ensureSocket = useCallback(async (): Promise<WebSocket> => {
    const current = socketRef.current;
    if (current && current.readyState === OPEN) return current;
    if (connectingRef.current) return connectingRef.current;
    dispatch({ type: "connection", status: stateRef.current.connection === "reconnecting" ? "reconnecting" : "connecting" });
    const promise = openSocket()
      .then((ws) => {
        dispatch({ type: "connection", status: "ready" });
        return ws;
      })
      .catch((error) => {
        dispatch({ type: "connection", status: "closed" });
        throw error;
      })
      .finally(() => {
        connectingRef.current = null;
      });
    connectingRef.current = promise;
    return promise;
  }, [dispatch, openSocket]);

  useEffect(() => {
    handleCloseRef.current = async (code: number) => {
      const running = stateRef.current.activeTurnId !== null;
      dispatch({ type: "connection", status: running ? "reconnecting" : "closed" });
      if (!running) return;

      const conversationId = stateRef.current.conversationId;
      if (!conversationId) {
        // Chưa nhận khung nào nên chưa biết hội thoại: không có gì để tải lại.
        dispatch({ type: "local_error", error: { code: "connection_lost", message: "Mất kết nối trước khi BE nhận câu hỏi." } });
      } else {
        dispatch({ type: "interrupt" });
      }
      if (code === 4429) {
        dispatch({ type: "connection", status: "closed" });
        dispatch({ type: "local_error", error: { code: "rate_limited", message: "Quá nhiều kết nối đồng thời." } });
        return;
      }

      const generation = generationRef.current;
      const delays = optionsRef.current.backoffMs ?? DEFAULT_BACKOFF;
      for (const delay of delays) {
        await sleep(delay);
        if (!aliveRef.current || generation !== generationRef.current) return;
        try {
          await ensureSocket();
          const id = stateRef.current.conversationId;
          if (id) {
            await loadConversation(id);
            void pollInterrupted(id);
          }
          return;
        } catch (error) {
          dispatch({ type: "connection", status: "reconnecting" });
          if (error instanceof AssistantError && error.code === "rate_limited") break;
        }
      }
      dispatch({ type: "connection", status: "closed" });
      dispatch({
        type: "local_error",
        error: { code: "connection_failed", message: "Không nối lại được với BE. Bấm \"Tải lại\" để thử lại." },
      });
    };
  });

  const ask = useCallback(
    async (question: string, page?: CurrentPageRef | null) => {
      const text = question.trim();
      if (!text || stateRef.current.activeTurnId) return;
      const turnId = (optionsRef.current.newTurnId ?? (() => crypto.randomUUID()))();
      dispatch({ type: "ask", turnId, question: text });
      try {
        const ws = await ensureSocket();
        const frame: ClientFrame = {
          type: "ask",
          conversation_id: stateRef.current.conversationId,
          turn_id: turnId,
          question: text,
          ...(page ? { page } : {}),
        };
        ws.send(JSON.stringify(frame));
      } catch (error) {
        dispatch({ type: "local_error", error: toUiError(error) });
      }
    },
    [dispatch, ensureSocket],
  );

  const cancel = useCallback(() => {
    const turnId = stateRef.current.activeTurnId;
    const ws = socketRef.current;
    if (!turnId || !ws || ws.readyState !== OPEN) return;
    dispatch({ type: "cancel_requested", turnId });
    ws.send(JSON.stringify({ type: "cancel", turn_id: turnId } satisfies ClientFrame));
  }, [dispatch]);

  const newConversation = useCallback(() => {
    generationRef.current += 1;
    dispatch({ type: "new_conversation" });
  }, [dispatch]);

  const openConversation = useCallback(
    async (id: string) => {
      generationRef.current += 1;
      dispatch({ type: "open_conversation", id });
      await loadConversation(id);
    },
    [dispatch, loadConversation],
  );

  const reload = useCallback(async () => {
    const id = stateRef.current.conversationId;
    if (id) await loadConversation(id);
  }, [loadConversation]);

  const dismissNotice = useCallback(() => dispatch({ type: "dismiss_notice" }), [dispatch]);

  useEffect(() => {
    aliveRef.current = true;
    refreshConversations();
    return () => {
      aliveRef.current = false;
      const ws = socketRef.current;
      socketRef.current = null;
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [refreshConversations]);

  // Làm mới danh sách hội thoại khi một lượt xong (hội thoại mới/đổi tiêu đề).
  const doneCount = state.turns.filter((turn) => turn.phase === "done").length;
  useEffect(() => {
    if (doneCount > 0) refreshConversations();
  }, [doneCount, refreshConversations]);

  return { state, conversations, ask, cancel, newConversation, openConversation, reload, dismissNotice };
}

function parseFrame(data: unknown): ServerFrame | null {
  if (typeof data !== "string") return null;
  try {
    const frame = JSON.parse(data) as ServerFrame;
    return frame && typeof frame.type === "string" ? frame : null;
  } catch {
    return null;
  }
}
