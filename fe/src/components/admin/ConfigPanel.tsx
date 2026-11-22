"use client";

import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { ANCHOR_LABEL } from "@/lib/labels";
import type { ExceptionType, MilestoneTemplate, Outcome } from "@/lib/types";
import FormDialog from "@/components/ui/dialog";
import SearchSelect from "@/components/ui/search-select";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, OkText, Page, Row, Table } from "@/components/ui/ui";

type Mode = "add" | "edit" | null;

// Cấu hình của QTV: mẫu mốc (9.1), chuẩn đầu ra theo khóa (Q5), danh mục loại ngoại lệ (Q2, D13).
// Thêm/sửa theo cùng kiểu với màn LMS: nút "Thêm" mở popup trống; nút "Sửa" mở popup có ô chọn mã (tìm kiếm, không gõ tự do)
// và điền sẵn dữ liệu của mã đó để sửa.
export default function ConfigPanel() {
  return (
    <Page title="Cấu hình">
      <Templates />
      <Outcomes />
      <ExceptionTypes />
    </Page>
  );
}

function Templates() {
  const state = useApi<MilestoneTemplate[]>("/api/config/milestone-templates");
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [anchor, setAnchor] = useState<MilestoneTemplate["anchor"]>("start");
  const [offset, setOffset] = useState("0");
  const save = useAction(() => {
    setOpen(false);
    state.reload();
  });
  const pick = (c: string) => {
    const t = state.data?.find((x) => x.code === c);
    if (!t) return;
    setCode(t.code);
    setName(t.name);
    setAnchor(t.anchor);
    setOffset(String(t.offset_days));
  };
  // Mẫu mốc chỉ sửa (không có thêm): mở popup với mốc đầu tiên chọn sẵn.
  const openEdit = () => {
    const first = state.data?.[0];
    if (!first) return;
    pick(first.code);
    save.clearError();
    setOpen(true);
  };
  return (
    <Card
      title="Mốc mẫu"
      className="bg-background"
      actions={
        <Button variant="primary" onClick={openEdit} disabled={!state.data?.length}>
          Sửa
        </Button>
      }
    >
      <Async state={state}>
        {(list) => (
          <Table head={["Mốc", "Tên", "Neo", "Lệch (ngày)"]}>
            {list.map((t) => (
              <tr key={t.code}>
                <td>{t.code}</td>
                <td>{t.name}</td>
                <td>{ANCHOR_LABEL[t.anchor] ?? t.anchor}</td>
                <td>{t.offset_days}</td>
              </tr>
            ))}
          </Table>
        )}
      </Async>
      <FormDialog title="Sửa mốc mẫu" open={open} onOpenChange={setOpen}>
        <Field label="Mã mốc" required>
          <SearchSelect options={(state.data ?? []).map((t) => ({ value: t.code, label: t.code }))} value={code} onChange={pick} placeholder="Tìm mốc..." />
        </Field>
        <Field label="Tên mốc" required>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Neo" required>
          <select value={anchor} onChange={(e) => setAnchor(e.target.value as MilestoneTemplate["anchor"])}>
            {Object.entries(ANCHOR_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Lệch (ngày)" required>
          <input type="number" value={offset} onChange={(e) => setOffset(e.target.value)} />
        </Field>
        <ErrorText message={save.error} />
        <Row>
          <Button disabled={save.busy || !code || !name.trim() || offset === ""} onClick={() => void save.run(() => send("PUT", `/api/admin/milestone-templates/${code}`, { name, anchor, offset_days: Number(offset) }))}>
            Lưu
          </Button>
          <Button onClick={() => setOpen(false)}>Hủy</Button>
        </Row>
      </FormDialog>
    </Card>
  );
}

function Outcomes() {
  const [cohort, setCohort] = useState("2026-K1");
  const state = useApi<Outcome[]>(`/api/config/outcomes?cohort=${encodeURIComponent(cohort)}`);
  const [mode, setMode] = useState<Mode>(null);
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const save = useAction(() => {
    setMode(null);
    state.reload();
  });
  const del = useAction(state.reload);
  const pick = (c: string) => {
    const o = state.data?.find((x) => x.code === c);
    if (!o) return;
    setCode(o.code);
    setDescription(o.description);
  };
  const openAdd = () => {
    setCode("");
    setDescription("");
    save.clearError();
    setMode("add");
  };
  const openEdit = () => {
    const first = state.data?.[0];
    if (!first) return;
    pick(first.code);
    save.clearError();
    setMode("edit");
  };
  const editing = mode === "edit";
  return (
    <Card
      title="Chuẩn đầu ra theo khóa"
      className="bg-background"
      actions={
        <>
          <Button variant="primary" onClick={openEdit} disabled={!state.data?.length}>
            Sửa
          </Button>
          <Button variant="primary" onClick={openAdd}>
            Thêm
          </Button>
        </>
      }
    >
      <Field label="Khóa">
        <input value={cohort} onChange={(e) => setCohort(e.target.value)} />
      </Field>
      <Async state={state}>
        {(list) =>
          list.length === 0 ? (
            <Empty>Khóa này chưa có chuẩn đầu ra.</Empty>
          ) : (
            <Table head={["Mã", "Mô tả", ""]}>
              {list.map((o) => (
                <tr key={o.id}>
                  <td>{o.code}</td>
                  <td>{o.description}</td>
                  <td>
                    <Button disabled={del.busy} onClick={() => void del.run(() => send("DELETE", `/api/admin/outcomes/${o.id}`))}>
                      Xóa
                    </Button>
                  </td>
                </tr>
              ))}
            </Table>
          )
        }
      </Async>
      <ErrorText message={del.error} />
      <FormDialog title={editing ? "Sửa chuẩn đầu ra" : "Thêm chuẩn đầu ra"} open={mode !== null} onOpenChange={(o) => !o && setMode(null)}>
        <Field label="Mã chuẩn đầu ra" required>
          {editing ? (
            <SearchSelect options={(state.data ?? []).map((o) => ({ value: o.code, label: o.code }))} value={code} onChange={pick} placeholder="Tìm chuẩn đầu ra..." />
          ) : (
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          )}
        </Field>
        <Field label="Mô tả" required>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <ErrorText message={save.error} />
        <Row>
          <Button disabled={save.busy || !code.trim() || !description.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/outcomes", { cohort, code, description }))}>
            Lưu
          </Button>
          <Button onClick={() => setMode(null)}>Hủy</Button>
        </Row>
      </FormDialog>
    </Card>
  );
}

function ExceptionTypes() {
  const state = useApi<ExceptionType[]>("/api/exception-types");
  const [mode, setMode] = useState<Mode>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [affects, setAffects] = useState(false);
  const [active, setActive] = useState(true);
  const [saved, setSaved] = useState<string | null>(null);
  const save = useAction(() => {
    setMode(null);
    setSaved("Đã lưu.");
    state.reload();
  });
  const toggle = useAction(state.reload);
  const pick = (c: string) => {
    const t = state.data?.find((x) => x.code === c);
    if (!t) return;
    setCode(t.code);
    setName(t.name);
    setAffects(t.affects_credit);
    setActive(t.active);
  };
  const openAdd = () => {
    setCode("");
    setName("");
    setAffects(false);
    setActive(true);
    save.clearError();
    setSaved(null);
    setMode("add");
  };
  const openEdit = () => {
    const first = state.data?.[0];
    if (!first) return;
    pick(first.code);
    save.clearError();
    setSaved(null);
    setMode("edit");
  };
  const editing = mode === "edit";
  return (
    <Card
      title="Loại ngoại lệ"
      className="bg-background"
      actions={
        <>
          <Button variant="primary" onClick={openEdit} disabled={!state.data?.length}>
            Sửa
          </Button>
          <Button variant="primary" onClick={openAdd}>
            Thêm
          </Button>
        </>
      }
    >
      <Async state={state}>
        {(list) => (
          <Table head={["Mã", "Tên", "Người duyệt", "Trạng thái", ""]}>
            {list.map((t) => (
              <tr key={t.code}>
                <td>{t.code}</td>
                <td>{t.name}</td>
                <td>{t.affects_credit ? <Badge tone="warn">Quản trị viên (ảnh hưởng tín chỉ)</Badge> : "Giảng viên"}</td>
                <td>{t.active ? "Đang dùng" : "Tắt"}</td>
                <td>
                  <Button disabled={toggle.busy} onClick={() => void toggle.run(() => send("PUT", "/api/admin/exception-types", { ...t, active: !t.active }))}>
                    {t.active ? "Tắt" : "Bật"}
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Async>
      <ErrorText message={toggle.error} />
      <OkText message={saved} />
      <FormDialog title={editing ? "Sửa loại ngoại lệ" : "Thêm loại ngoại lệ"} open={mode !== null} onOpenChange={(o) => !o && setMode(null)}>
        <Field label="Mã loại ngoại lệ" required>
          {editing ? (
            <SearchSelect options={(state.data ?? []).map((t) => ({ value: t.code, label: t.code }))} value={code} onChange={pick} placeholder="Tìm loại ngoại lệ..." />
          ) : (
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          )}
        </Field>
        <Field label="Tên loại ngoại lệ" required>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={affects} onChange={(e) => setAffects(e.target.checked)} /> Ảnh hưởng tín chỉ
        </label>
        <ErrorText message={save.error} />
        <Row>
          <Button disabled={save.busy || !code.trim() || !name.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/exception-types", { code, name, affects_credit: affects, active }))}>
            Lưu
          </Button>
          <Button onClick={() => setMode(null)}>Hủy</Button>
        </Row>
      </FormDialog>
    </Card>
  );
}
