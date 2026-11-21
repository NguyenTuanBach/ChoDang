"use client";

import { createContext, useContext } from "react";
import type { AuthUser } from "./auth";

// Người dùng đang đăng nhập, do AuthProvider cung cấp cho khung và các trang con.
export const UserContext = createContext<AuthUser | null>(null);

export function useCurrentUser(): AuthUser {
  const user = useContext(UserContext);
  if (!user) throw new Error("useCurrentUser phải dùng bên trong <AuthProvider>");
  return user;
}

// Phiên: người dùng + số thông báo chưa đọc + đăng xuất (dùng ở thanh bên và thanh trên).
export type Session = { user: AuthUser; unread: number; signOut: () => Promise<void> };

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession phải dùng bên trong <AuthProvider>");
  return session;
}
