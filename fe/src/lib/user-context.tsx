"use client";

import { createContext, useContext } from "react";
import type { AuthUser } from "./auth";

// Người dùng đang đăng nhập, do AuthGate cung cấp cho các trang con.
export const UserContext = createContext<AuthUser | null>(null);

export function useCurrentUser(): AuthUser {
  const user = useContext(UserContext);
  if (!user) throw new Error("useCurrentUser phải dùng bên trong <AuthGate>");
  return user;
}
