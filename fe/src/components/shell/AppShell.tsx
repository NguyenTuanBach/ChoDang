"use client";

import type { ReactNode } from "react";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import AssistantDock, { AssistantToggle } from "@/components/assistant/AssistantDock";
import AppSidebar from "./AppSidebar";
import SiteHeader from "./SiteHeader";

// Khung chung của mọi trang sau đăng nhập: thanh bên + thanh trên + nội dung. Nằm ở layout nên giữ nguyên khi chuyển trang.
export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider delayDuration={200}>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="min-w-0">
          <SiteHeader actions={<AssistantToggle />} />
          <div className="flex-1">{children}</div>
        </SidebarInset>
        <AssistantDock />
      </SidebarProvider>
    </TooltipProvider>
  );
}
