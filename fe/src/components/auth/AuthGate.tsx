"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { fetchMe, logout, ROLE_LABEL, type AuthUser, type Role } from "@/lib/auth";
import { HOME, NAV, type NavItem } from "@/lib/nav";
import { UserContext } from "@/lib/user-context";

const linkClass = (active: boolean) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${active ? "bg-blue-600 text-white" : "text-fg hover:bg-soft"}`;

// Mục đang chọn: khớp đúng đường dẫn, hoặc đường dẫn con của mục có từ 2 cấp trở lên (vd /student/outline).
function isActive(pathname: string, href: string) {
  return pathname === href || (href.split("/").length > 2 && pathname.startsWith(`${href}/`));
}

function NavLinks({ items, onNavigate }: { items: NavItem[]; onNavigate: () => void }) {
  const pathname = usePathname(); // phải nằm trong <Suspense> (route động)
  return (
    <>
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={linkClass(active)} onClick={onNavigate}>
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

// Menu khi chưa biết đường dẫn hiện tại (lúc đang dựng trước): chưa tô mục đang chọn.
function PlainLinks({ items }: { items: NavItem[] }) {
  return (
    <>
      {items.map((item) => (
        <Link key={item.href} href={item.href} className={linkClass(false)}>
          {item.label}
        </Link>
      ))}
    </>
  );
}

type Props = {
  children: ReactNode;
  fetchImpl?: typeof fetch;
  // Chỉ các vai trò này vào được trang; vai trò khác bị chuyển về trang chủ của họ. Bỏ trống = mọi vai trò.
  roles?: Role[];
};

// Chặn trang cho người chưa đăng nhập (chuyển sang /login), kiểm vai trò, hiện thanh "menu · thông báo · tên · vai trò · Đăng xuất"
// và cung cấp người dùng cho trang con qua useCurrentUser().
export default function AuthGate({ children, fetchImpl, roles }: Props) {
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchMe(fetchImpl)
      .then((me) => {
        if (cancelled) return;
        if (!me) router.replace("/login");
        else if (roles && !roles.includes(me.role)) router.replace(HOME[me.role]);
        else setUser(me);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Không kết nối được BE");
      });
    return () => {
      cancelled = true;
    };
  }, [fetchImpl, router, roles]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (fetchImpl ?? fetch)("/api/notifications", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body: { unread?: number } | null) => {
        if (!cancelled) setUnread(body?.unread ?? 0);
      })
      .catch(() => undefined); // thông báo không chặn trang
    return () => {
      cancelled = true;
    };
  }, [user, fetchImpl]);

  async function signOut() {
    try {
      await logout(fetchImpl);
    } catch {
      // phiên có thể đã hết hạn: vẫn về trang đăng nhập
    }
    router.replace("/login");
  }

  if (error) {
    return (
      <p role="alert" className="mx-auto my-12 max-w-2xl px-4 text-red-700">
        Không kiểm tra được phiên đăng nhập: {error}
      </p>
    );
  }
  if (!user) return <p className="mx-auto my-12 max-w-2xl px-4 text-muted">Đang kiểm tra đăng nhập...</p>;

  return (
    <UserContext.Provider value={user}>
      <header className="sticky top-0 z-20 border-b border-border bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
          <Link href={HOME[user.role]} className="mr-2 text-base font-bold tracking-tight text-blue-600">
            VIN-15
          </Link>
          <button
            type="button"
            className="ml-auto rounded-lg border border-border px-2.5 py-1 text-sm md:hidden"
            aria-expanded={menuOpen}
            aria-controls="main-menu"
            onClick={() => setMenuOpen((open) => !open)}
          >
            ☰ Menu
          </button>
          <nav
            id="main-menu"
            aria-label="Menu chính"
            className={`${menuOpen ? "flex" : "hidden"} order-last w-full flex-col gap-1 md:order-none md:flex md:w-auto md:flex-1 md:flex-row md:flex-wrap`}
          >
            <Suspense fallback={<PlainLinks items={NAV[user.role]} />}>
              <NavLinks items={NAV[user.role]} onNavigate={() => setMenuOpen(false)} />
            </Suspense>
          </nav>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Link href="/notifications" className="relative rounded-lg px-2.5 py-1.5 font-medium hover:bg-soft">
              Thông báo
              {unread > 0 && (
                <span className="ml-1.5 inline-flex min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 text-xs font-semibold text-white">{unread}</span>
              )}
            </Link>
            <strong className="font-semibold">{user.full_name || user.email}</strong>
            <span className="rounded-full bg-soft px-2.5 py-0.5 text-xs text-muted ring-1 ring-inset ring-border">{ROLE_LABEL[user.role]}</span>
            <button
              type="button"
              className="rounded-lg border border-border px-3 py-1 text-sm font-medium hover:bg-soft"
              onClick={() => void signOut()}
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </header>
      {children}
    </UserContext.Provider>
  );
}
