"use client";

import { useCallback, useEffect, useState } from "react";
import { api, messageOf } from "./http";

type State<T> = { data: T | null; error: string | null; loading: boolean };

// Tải dữ liệu từ BE; `path = null` để tạm dừng. `reload()` tải lại sau khi thực hiện một thao tác.
export function useApi<T>(path: string | null) {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: path !== null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    api<T>(path)
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false });
      })
      .catch((e: unknown) => {
        if (!cancelled) setState((s) => ({ ...s, error: messageOf(e), loading: false }));
      });
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}

// Chạy một thao tác ghi: theo dõi đang chạy / lỗi, gọi `onDone` khi thành công.
export function useAction(onDone?: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (action: () => Promise<unknown>) => {
      setBusy(true);
      setError(null);
      try {
        await action();
        onDone?.();
        return true;
      } catch (e) {
        setError(messageOf(e));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [onDone],
  );

  return { run, busy, error, clearError: () => setError(null) };
}
