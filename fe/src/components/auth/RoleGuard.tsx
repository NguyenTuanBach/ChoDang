"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import type { Role } from "@/lib/auth";
import { HOME } from "@/lib/nav";
import { useCurrentUser } from "@/lib/user-context";

// Chỉ cho các vai trò trong `roles` xem phần con; vai trò khác bị chuyển về trang chủ của họ (không lộ nội dung trang).
export default function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const router = useRouter();
  const user = useCurrentUser();
  const allowed = roles.includes(user.role);

  useEffect(() => {
    if (!allowed) router.replace(HOME[user.role]);
  }, [allowed, router, user.role]);

  return allowed ? <>{children}</> : null;
}
