import type { ReactNode } from "react";
import RoleGuard from "@/components/auth/RoleGuard";

export default function Layout({ children }: { children: ReactNode }) {
  return <RoleGuard roles={["admin"]}>{children}</RoleGuard>;
}
