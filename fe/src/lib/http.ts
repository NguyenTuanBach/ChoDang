// Gọi API BE cùng origin (/api/..., Next rewrites). Phiên là cookie HttpOnly nên không cần gắn token.

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Fetch = typeof fetch;

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { message?: string; detail?: unknown };
    if (body.message) return body.message;
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return "Dữ liệu gửi lên chưa hợp lệ";
  } catch {
    // không phải JSON: dùng mô tả mặc định
  }
  return `HTTP ${response.status}`;
}

export async function api<T = void>(path: string, init: RequestInit = {}, fetchImpl: Fetch = fetch): Promise<T> {
  const response = await fetchImpl(path, { cache: "no-store", ...init });
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function send<T = void>(method: "POST" | "PUT" | "DELETE" | "PATCH", path: string, body?: unknown, fetchImpl: Fetch = fetch): Promise<T> {
  return api<T>(
    path,
    {
      method,
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    fetchImpl,
  );
}

export function upload<T = void>(path: string, file: File, fields: Record<string, string> = {}, fetchImpl: Fetch = fetch): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return api<T>(path, { method: "POST", body: form }, fetchImpl);
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Có lỗi xảy ra";
}

// Chuỗi truy vấn bỏ qua giá trị rỗng.
export function query(params: Record<string, string | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "" || value === false) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
