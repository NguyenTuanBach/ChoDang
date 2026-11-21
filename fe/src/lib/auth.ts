// Xác thực phía trình duyệt: gọi /api/auth/* cùng origin (Next rewrites sang BE). Phiên là cookie HttpOnly do BE đặt,
// nên FE không đọc hay giữ token.

export type Role = "admin" | "lecturer" | "student";

export type AuthUser = { id: string; email: string; full_name: string; role: Role };

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Quản trị viên",
  lecturer: "Giảng viên",
  student: "Sinh viên",
};

type Fetch = typeof fetch;

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { message?: string };
    if (body.message) return body.message;
  } catch {
    // không phải JSON: dùng mô tả mặc định
  }
  return `HTTP ${response.status}`;
}

// Người dùng đang đăng nhập; null khi chưa đăng nhập (401). Lỗi khác (BE sập...) thì ném.
export async function fetchMe(fetchImpl: Fetch = fetch): Promise<AuthUser | null> {
  const response = await fetchImpl("/api/auth/me", { cache: "no-store" });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as AuthUser;
}

// Tài khoản mẫu để đăng nhập dev; null khi BE không bật đăng nhập dev (production trả 404).
export async function listDevAccounts(fetchImpl: Fetch = fetch): Promise<AuthUser[] | null> {
  const response = await fetchImpl("/api/auth/dev-accounts", { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as AuthUser[];
}

export async function devLogin(email: string, fetchImpl: Fetch = fetch): Promise<AuthUser> {
  const response = await fetchImpl("/api/auth/dev-login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as AuthUser;
}

// Cách đăng nhập đang bật ở BE. Lỗi hoặc dữ liệu lạ thì coi như chưa bật Google (không chặn trang đăng nhập).
export async function fetchProviders(fetchImpl: Fetch = fetch): Promise<{ google: boolean }> {
  try {
    const response = await fetchImpl("/api/auth/providers", { cache: "no-store" });
    if (!response.ok) return { google: false };
    const body = (await response.json()) as { google?: unknown };
    return { google: body?.google === true };
  } catch {
    return { google: false };
  }
}

export async function logout(fetchImpl: Fetch = fetch): Promise<void> {
  const response = await fetchImpl("/api/auth/logout", { method: "POST" });
  if (!response.ok) throw new Error(await readError(response));
}
