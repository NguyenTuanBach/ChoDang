import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { EXTRA_PAGES, NAV, findCurrent, groupNav, isActive, pageHref } from "./nav";

type Catalog = Record<string, { key: string; label: string }[] | string>;

// Danh mục trang của trợ lý (agent) — khóa phải khớp NAV, vì FE là nơi duy nhất giữ URL.
const catalog = JSON.parse(readFileSync(path.resolve(__dirname, "../../../agent/src/vin15_agent/policy_assistant/pages.json"), "utf-8")) as Catalog;
const pages = (role: string) => catalog[role] as { key: string; label: string }[];

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

  it("groupNav giữ thứ tự nhóm", () => {
    expect(groupNav(NAV.student).map((g) => g.group)).toEqual(["Chung", "Thực tập", "Yêu cầu", "Kết quả"]);
  });
});
