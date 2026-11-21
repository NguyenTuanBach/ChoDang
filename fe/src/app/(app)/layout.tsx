import type { ReactNode } from "react";
import AssistantProvider from "@/components/assistant/AssistantProvider";
import AuthProvider from "@/components/auth/AuthProvider";
import AppShell from "@/components/shell/AppShell";

// Khung dùng chung cho mọi trang sau đăng nhập (sinh viên, giảng viên, quản trị, dashboard, thông báo, trợ lý).
// Layout giữ nguyên khi chuyển trang: thanh bên (và ngăn Trợ lý) không bị dựng lại.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AssistantProvider>
        <AppShell>{children}</AppShell>
      </AssistantProvider>
    </AuthProvider>
  );
}
