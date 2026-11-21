"use client";

import { GraduationCap } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { HOME, NAV, groupNav, isActive } from "@/lib/nav";
import { useCurrentUser } from "@/lib/user-context";
import UserMenu from "./UserMenu";

// Danh sách mục: cần đường dẫn hiện tại (route động) nên phải nằm trong <Suspense>; `pathname` rỗng = chưa tô mục đang chọn.
function NavGroups({ pathname }: { pathname: string }) {
  const user = useCurrentUser();
  const { setOpenMobile } = useSidebar();
  return (
    <>
      {groupNav(NAV[user.role]).map(({ group, items }) => (
        <SidebarGroup key={group}>
          <SidebarGroupLabel>{group}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <SidebarMenuItem key={item.key}>
                    <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
                      <Link href={item.href} aria-current={active ? "page" : undefined} onClick={() => setOpenMobile(false)}>
                        <item.icon />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  );
}

function CurrentNavGroups() {
  return <NavGroups pathname={usePathname()} />;
}

export default function AppSidebar() {
  const user = useCurrentUser();
  return (
    <Sidebar variant="inset" collapsible="icon" aria-label="Menu chính">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="VIN-15">
              <Link href={HOME[user.role]}>
                <span className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <GraduationCap className="size-5" />
                </span>
                <span className="grid flex-1 text-left leading-tight">
                  <span className="truncate text-sm font-semibold">VIN-15</span>
                  <span className="truncate text-xs opacity-70">Quản lý thực tập</span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <Suspense fallback={<NavGroups pathname="" />}>
          <CurrentNavGroups />
        </Suspense>
      </SidebarContent>
      <SidebarFooter>
        <UserMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
