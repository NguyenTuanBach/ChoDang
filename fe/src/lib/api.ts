// Gọi BE từ phía server (Server Component). Phía trình duyệt dùng đường dẫn tương đối /api/... (xem rewrites trong next.config.ts).
export const BE_URL = process.env.BE_URL ?? "http://localhost:8000";

export type ReadinessResponse = { status: string; components: Record<string, string> };

export type AgentHealthResponse = {
  status: string;
  detail: string;
  agent: { service: string; version: string; agents: string[]; llm_providers: string[] } | null;
};

export type Result<T> = { ok: true; data: T } | { ok: false; error: string };

// BE trả 503 kèm JSON khi thành phần nào đó DOWN: vẫn coi là có dữ liệu để hiển thị.
export async function getFromBackend<T>(path: string): Promise<Result<T>> {
  try {
    const response = await fetch(`${BE_URL}${path}`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    return { ok: true, data: (await response.json()) as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Không kết nối được BE" };
  }
}
