import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DETAIL_PAGES, EXTRA_PAGES, NAV, currentPageRef, findCurrent, groupNav, isActive, pageHref } from "./nav";

type AgentPage = { key: string; label: string; menu?: boolean; param?: string; filters?: Record<string, { values: string[] }> };
type Catalog = Record<string, AgentPage[] | string>;

// Danh mục trang của trợ lý (agent) — khóa phải khớp NAV, vì FE là nơi duy nhất giữ URL.
const catalog = JSON.parse(readFileSync(path.resolve(__dirname, "../../../agent/src/vin15_agent/policy_assistant/pages.json"), "utf-8")) as Catalog;
const allPages = (role: string) => catalog[role] as AgentPage[];
const pages = (role: string) => allPages(role).filter((p) => p.menu !== false); // trang trong menu (NAV)
const detailPages = (role: string) => allPages(role).filter((p) => p.menu === false);

describe("khóa trang của trợ lý khớp menu (agent pages.json ↔ nav.ts)", () => {
  for (const role of ["student", "lecturer", "admin"] as const) {
    it(`${role}: cùng tập khóa và cùng nhãn với menu`, () => {
      const nav = Object.fromEntries(NAV[role].map((i) => [i.key, i.label]));
      const agent = Object.fromEntries(pages(role).map((p) => [p.key, p.label]));
      expect(agent).toEqual(nav);
    });

    it(`${role}: mỗi khóa của trợ lý đổi được sang đường dẫn`, () => {
      for (const p of [...pages(role), ...pages("common")]) {
        const target = pageHref(role, p.key);
        expect(target, `${role}/${p.key}`).not.toBeNull();
        expect(target?.href.startsWith("/")).toBe(true);
      }
    });

    it(`${role}: trang ngoài menu (cần mã hồ sơ) khớp DETAIL_PAGES`, () => {
      const agent = Object.fromEntries(detailPages(role).map((p) => [p.key, p.label]));
      expect(agent).toEqual(Object.fromEntries(DETAIL_PAGES[role].map((d) => [d.key, d.label])));
      for (const p of detailPages(role)) {
        expect(p.param).toBe("internship_id");
        expect(pageHref(role, p.key, { internshipId: 7 })?.href).toMatch(/\/internships\/7$/);
      }
    });

    it(`${role}: khóa bộ lọc của trợ lý khớp khóa trang đọc từ query`, () => {
      for (const p of pages(role)) {
        const nav = NAV[role].find((i) => i.key === p.key);
        expect(Object.keys(p.filters ?? {}).sort(), `${role}/${p.key}`).toEqual([...(nav?.filters ?? [])].sort());
      }
    });
  }

  it("trang chung khớp EXTRA_PAGES", () => {
    expect(Object.fromEntries(pages("common").map((p) => [p.key, p.label]))).toEqual(Object.fromEntries(EXTRA_PAGES.map((p) => [p.key, p.label])));
  });
});

describe("nav", () => {
  it("khóa trong một vai trò là duy nhất", () => {
    for (const items of Object.values(NAV)) expect(new Set(items.map((i) => i.key)).size).toBe(items.length);
  });

  it("khóa của vai trò khác hoặc khóa lạ không đổi được sang đường dẫn", () => {
    expect(pageHref("student", "audit")).toBeNull();
    expect(pageHref("student", "flags")).toBeNull();
    expect(pageHref("lecturer", "outline")).toBeNull();
    expect(pageHref("admin", "../etc")).toBeNull();
    expect(pageHref("student", "")).toBeNull();
  });

  it("đường dẫn mọi mục thuộc đúng vùng của vai trò (trừ dashboard dùng chung)", () => {
    const zone = { student: "/student", lecturer: "/lecturer", admin: "/admin" } as const;
    for (const [role, items] of Object.entries(NAV)) {
      for (const item of items) {
        if (item.key === "dashboard") expect(item.href).toBe("/dashboard");
        else expect(item.href.startsWith(zone[role as keyof typeof zone])).toBe(true);
      }
    }
  });

  it("isActive/findCurrent chọn mục dài nhất", () => {
    expect(isActive("/student", "/student")).toBe(true);
    expect(isActive("/student/outline", "/student")).toBe(false); // mục 1 cấp chỉ khớp đúng
    expect(isActive("/lecturer/internships/5", "/lecturer/internships")).toBe(true);
    expect(findCurrent("lecturer", "/lecturer/internships/5")?.label).toBe("Hồ sơ");
    expect(findCurrent("student", "/notifications")?.label).toBe("Thông báo");
    expect(findCurrent("student", "/khong-co")).toBeNull();
  });

  it("trang chi tiết cần mã hồ sơ hợp lệ", () => {
    expect(pageHref("lecturer", "internship_detail", { internshipId: 12 })).toEqual({ href: "/lecturer/internships/12", label: "Chi tiết hồ sơ" });
    expect(pageHref("admin", "internship_detail", { internshipId: 3 })?.href).toBe("/admin/internships/3");
    expect(pageHref("lecturer", "internship_detail")).toBeNull();
    expect(pageHref("lecturer", "internship_detail", { internshipId: -1 })).toBeNull();
    expect(pageHref("lecturer", "internship_detail", { internshipId: 1.5 })).toBeNull();
    expect(pageHref("student", "internship_detail", { internshipId: 12 })).toBeNull();
  });

  it("bộ lọc chỉ giữ khóa trang khai báo, giá trị được mã hóa", () => {
    expect(pageHref("lecturer", "flags", { filters: { status: "resolved" } })?.href).toBe("/lecturer/flags?status=resolved");
    expect(pageHref("lecturer", "queue", { filters: { kind: "outline", status: "x" } })?.href).toBe("/lecturer?kind=outline");
    expect(pageHref("admin", "internships", { filters: { status: "in_progress", flagged: "true" } })?.href).toBe("/admin/internships?status=in_progress&flagged=true");
    expect(pageHref("lecturer", "internships", { filters: { status: "a&b=c" } })?.href).toBe("/lecturer/internships?status=a%26b%3Dc");
    expect(pageHref("lecturer", "students", { filters: { status: "x" } })?.href).toBe("/lecturer/students"); // trang không có bộ lọc
    expect(pageHref("lecturer", "flags", { filters: null })?.href).toBe("/lecturer/flags");
  });

  it("currentPageRef: khóa trang đang mở và mã hồ sơ ở trang chi tiết", () => {
    expect(currentPageRef("lecturer", "/lecturer/internships/42")).toEqual({ key: "internship_detail", internship_id: 42 });
    expect(currentPageRef("lecturer", "/lecturer/internships")).toEqual({ key: "internships" });
    expect(currentPageRef("student", "/student/outline")).toEqual({ key: "outline" });
    expect(currentPageRef("student", "/assistant")).toEqual({ key: "assistant" });
    expect(currentPageRef("student", "/khong-co")).toBeNull();
  });

  it("groupNav giữ thứ tự nhóm", () => {
    expect(groupNav(NAV.student).map((g) => g.group)).toEqual(["Chung", "Thực tập", "Yêu cầu", "Kết quả"]);
  });
});
