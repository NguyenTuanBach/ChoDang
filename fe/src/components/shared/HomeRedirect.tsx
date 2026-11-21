"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { HOME } from "@/lib/nav";
import { useCurrentUser } from "@/lib/user-context";

// Trang chủ "/": chuyển người dùng về trang đầu của vai trò.
export default function HomeRedirect() {
  const user = useCurrentUser();
  const router = useRouter();
  useEffect(() => {
    router.replace(HOME[user.role]);
  }, [user.role, router]);
  return <p style={{ padding: "2rem 1rem" }}>Đang chuyển trang...</p>;
}
