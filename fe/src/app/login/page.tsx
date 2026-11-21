import type { Metadata } from "next";
import LoginPanel from "@/components/auth/LoginPanel";

export const metadata: Metadata = {
  title: "Đăng nhập | VIN-15",
};

export default function LoginPage() {
  return <LoginPanel />;
}
