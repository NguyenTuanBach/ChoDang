"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, Fragment } from "react";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ROLE_LABEL } from "@/lib/auth";
import { findCurrent } from "@/lib/nav";
import { useSession } from "@/lib/user-context";

function Crumbs({ pathname }: { pathname: string }) {
  const { user } = useSession();
  const current = findCurrent(user.role, pathname);
  const trail = [ROLE_LABEL[user.role], ...(current?.group ? [current.group] : []), ...(current ? [current.label] : [])];
  return (
    <Breadcrumb className="min-w-0">
      <BreadcrumbList className="flex-nowrap">
        {trail.map((label, i) => (
          <Fragment key={`${label}-${i}`}>
            {i > 0 && <BreadcrumbSeparator className={i < trail.length - 1 ? "hidden sm:block" : undefined} />}
            <BreadcrumbItem className={i < trail.length - 1 ? "hidden sm:inline-flex" : "min-w-0"}>
              {i === trail.length - 1 ? <BreadcrumbPage className="truncate font-medium">{label}</BreadcrumbPage> : <span className="text-muted-foreground">{label}</span>}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

function CurrentCrumbs() {
  return <Crumbs pathname={usePathname()} />;
}

// Chuông thông báo kèm số chưa đọc.
function NotificationsBell() {
  const { unread } = useSession();
  return (
    <Link
      href="/notifications"
      aria-label={unread > 0 ? `Thông báo (${unread} chưa đọc)` : "Thông báo"}
      className="relative inline-flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <Bell className="size-5" />
      {unread > 0 && (
        <span className="absolute right-0.5 top-0.5 inline-flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-4 text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}

export default function SiteHeader({ actions }: { actions?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 rounded-t-xl border-b border-border bg-background/85 px-4 backdrop-blur">
      <SidebarTrigger className="-ml-1" aria-label="Thu gọn / mở menu" />
      <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />
      <Suspense fallback={<Crumbs pathname="" />}>
        <CurrentCrumbs />
      </Suspense>
      <div className="ml-auto flex items-center gap-1">
        {actions}
        <NotificationsBell />
      </div>
    </header>
  );
}
