"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { buttonVariants } from "@/components/ui/button";
import { fetchMe, type AuthUser } from "@/lib/auth";
import { HOME } from "@/lib/nav";
import { cn } from "@/lib/utils";

// Nút vào hệ thống: nhãn luôn là "Đăng nhập"; đã đăng nhập thì tới trang đầu của vai trò, chưa thì tới /login.
export default function LandingCta({ size = "lg" }: { size?: "default" | "lg" }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  const href = user ? HOME[user.role] : "/login";
  return (
    <Link href={href} className={cn(buttonVariants({ size }), "border-2 border-foreground/25 bg-card px-4 text-foreground hover:bg-secondary")}>
      Đăng nhập
    </Link>
  );
}
