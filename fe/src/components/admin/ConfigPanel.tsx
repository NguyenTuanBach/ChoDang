"use client";

import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { ANCHOR_LABEL } from "@/lib/labels";
import type { ExceptionType, MilestoneTemplate, Outcome } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, OkText, Page, Row, Table } from "@/components/ui/ui";

// Cấu hình của QTV: mẫu mốc (9.1), chuẩn đầu ra theo khóa (Q5), danh mục loại ngoại lệ (Q2, D13).
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
  return (
    <Card title="Mốc mẫu">
      <p>
        <small>Hạn mốc = ngày neo + số ngày lệch. Thay đổi áp dụng cho hồ sơ được xác nhận từ sau đó.</small>
      </p>
      <Async state={state}>
        {(list) => (
          <Table head={["Mốc", "Tên", "Neo", "Lệch (ngày)", ""]}>
            {list.map((t) => (
              <TemplateRow key={t.code} template={t} reload={state.reload} />
            ))}
          </Table>
        )}
      </Async>
    </Card>
  );
}

function TemplateRow({ template: t, reload }: { template: MilestoneTemplate; reload: () => void }) {
  const [name, setName] = useState(t.name);
  const [anchor, setAnchor] = useState(t.anchor);
  const [offset, setOffset] = useState(String(t.offset_days));
  const action = useAction(reload);
  return (
    <tr>
      <td>{t.code}</td>
      <td>
        <input value={name} onChange={(e) => setName(e.target.value)} size={30} />
      </td>
      <td>
        <select value={anchor} onChange={(e) => setAnchor(e.target.value as MilestoneTemplate["anchor"])}>
          {Object.entries(ANCHOR_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </td>
      <td>
        <input type="number" value={offset} onChange={(e) => setOffset(e.target.value)} style={{ width: "5rem" }} />
      </td>
      <td>
        <Button disabled={action.busy} onClick={() => void action.run(() => send("PUT", `/api/admin/milestone-templates/${t.code}`, { name, anchor, offset_days: Number(offset) }))}>
          Lưu
        </Button>
        <ErrorText message={action.error} />
      </td>
    </tr>
  );
}

function Outcomes() {
  const [cohort, setCohort] = useState("2026-K1");
  const state = useApi<Outcome[]>(`/api/config/outcomes?cohort=${encodeURIComponent(cohort)}`);
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const add = useAction(() => {
    setCode("");
    setDescription("");
    state.reload();
  });
  const del = useAction(state.reload);
  return (
    <Card title="Chuẩn đầu ra theo khóa">
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
      <Row>
        <input placeholder="Mã (LO5)" value={code} onChange={(e) => setCode(e.target.value)} size={8} />
        <input placeholder="Mô tả chuẩn đầu ra" value={description} onChange={(e) => setDescription(e.target.value)} size={50} />
        <Button variant="primary" disabled={add.busy || !code.trim() || !description.trim()} onClick={() => void add.run(() => send("PUT", "/api/admin/outcomes", { cohort, code, description }))}>
          Thêm / sửa
        </Button>
      </Row>
      <ErrorText message={add.error} />
    </Card>
  );
}

function ExceptionTypes() {
  const state = useApi<ExceptionType[]>("/api/exception-types");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [affects, setAffects] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const save = useAction(() => {
    setCode("");
    setName("");
    setSaved("Đã lưu.");
    state.reload();
  });
  const toggle = useAction(state.reload);
  return (
    <Card title="Loại ngoại lệ">
      <p>
        <small>Loại “ảnh hưởng tín chỉ” do quản trị viên duyệt; loại thường do giảng viên duyệt.</small>
      </p>
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
      <Row>
        <input placeholder="Mã (vd: change_unit)" value={code} onChange={(e) => setCode(e.target.value)} size={18} />
        <input placeholder="Tên loại ngoại lệ" value={name} onChange={(e) => setName(e.target.value)} size={30} />
        <label>
          <input type="checkbox" checked={affects} onChange={(e) => setAffects(e.target.checked)} /> Ảnh hưởng tín chỉ
        </label>
        <Button variant="primary" disabled={save.busy || !code.trim() || !name.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/exception-types", { code, name, affects_credit: affects, active: true }))}>
          Thêm
        </Button>
      </Row>
      <ErrorText message={save.error} />
      <OkText message={saved} />
    </Card>
  );
}
