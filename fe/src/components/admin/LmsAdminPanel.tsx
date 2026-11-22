"use client";

import { useState } from "react";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import type { Course, LmsStudent, SyncJob } from "@/lib/types";
import FormDialog from "@/components/ui/dialog";
import SearchSelect from "@/components/ui/search-select";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, FilePicker, OkText, Page, Row, Table } from "@/components/ui/ui";

// Giao diện của LMS mini: học phần, tiên quyết, sinh viên, điểm, nhập CSV và theo dõi đồng bộ kết quả quy đổi tín chỉ (D5, D6).
export default function LmsAdminPanel() {
  return (
    <Page title="LMS (học phần, điểm, tín chỉ)">
      <SyncJobs />
      <Courses />
      <Students />
      <Grades />
    </Page>
  );
}

function SyncJobs() {
  const state = useApi<SyncJob[]>("/api/admin/lms/sync-jobs");
  const retry = useAction(state.reload);
  return (
    <Card title="Đồng bộ kết quả quy đổi sang LMS" className="bg-background">
      <Async state={state}>
        {(jobs) =>
          jobs.length === 0 ? (
            <Empty>Chưa có kết quả nào cần đồng bộ (chỉ tạo sau khi QTV phê duyệt công nhận).</Empty>
          ) : (
            <Table head={["Sinh viên", "Mã SV", "Học phần", "Tín chỉ", "Trạng thái", "Lần thử", "Lỗi", ""]}>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.student_name}</td>
                  <td>{j.student_code}</td>
                  <td>{j.course_code}</td>
                  <td>{j.credits}</td>
                  <td>
                    <Badge tone={j.status === "synced" ? "good" : j.status === "failed" ? "bad" : "warn"}>{j.status}</Badge>
                  </td>
                  <td>{j.attempts}</td>
                  <td>{j.last_error}</td>
                  <td>{j.status === "failed" && <Button disabled={retry.busy} onClick={() => void retry.run(() => send("POST", `/api/admin/lms/sync-jobs/${j.id}/retry`))}>Thử lại</Button>}</td>
                </tr>
              ))}
            </Table>
          )
        }
      </Async>
      <ErrorText message={retry.error} />
    </Card>
  );
}

function Courses() {
  const state = useApi<Course[]>("/api/lms/courses");
  const [form, setForm] = useState({ code: "", name: "", credits: "3", kind: "regular" });
  // "add": các trường trống để thêm mới; "edit": điền sẵn dữ liệu của dòng đang sửa (mã là khóa nên khóa lại).
  const [mode, setMode] = useState<"add" | "edit" | null>(null);
  const save = useAction(() => {
    setMode(null);
    state.reload();
  });
  const openAdd = () => {
    setForm({ code: "", name: "", credits: "3", kind: "regular" });
    save.clearError();
    setMode("add");
  };
  const pick = (code: string) => {
    const c = state.data?.find((x) => x.code === code);
    if (c) setForm({ code: c.code, name: c.name, credits: String(c.credits), kind: c.kind });
  };
  // Mở popup sửa với học phần đầu tiên chọn sẵn để các trường đã có dữ liệu; đổi học phần bằng ô chọn có tìm kiếm.
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
      title="Học phần"
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
          <Table head={["Mã", "Tên", "Tín chỉ", "Loại"]}>
            {list.map((c) => (
              <tr key={c.code}>
                <td>{c.code}</td>
                <td>{c.name}</td>
                <td>{c.credits}</td>
                <td>{c.kind === "internship" ? "Thực tập" : "Thường"}</td>
              </tr>
            ))}
          </Table>
        )}
      </Async>
      <FormDialog title={editing ? "Sửa học phần" : "Thêm học phần"} open={mode !== null} onOpenChange={(o) => !o && setMode(null)}>
        <Field label="Mã học phần" required>
          {editing ? (
            <SearchSelect options={(state.data ?? []).map((c) => ({ value: c.code, label: c.code }))} value={form.code} onChange={pick} placeholder="Tìm học phần..." />
          ) : (
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          )}
        </Field>
        <Field label="Tên học phần" required>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Số tín chỉ" required>
          <input type="number" min={1} value={form.credits} onChange={(e) => setForm({ ...form, credits: e.target.value })} />
        </Field>
        <Field label="Loại">
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            <option value="regular">Thường</option>
            <option value="internship">Thực tập</option>
          </select>
        </Field>
        <ErrorText message={save.error} />
        <Row>
          <Button disabled={save.busy || !form.code.trim() || !form.name.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/lms/courses", { ...form, credits: Number(form.credits) }))}>
            Lưu
          </Button>
          <Button onClick={() => setMode(null)}>Hủy</Button>
        </Row>
      </FormDialog>
      <Prerequisites courses={state.data ?? []} />
    </Card>
  );
}

function Prerequisites({ courses }: { courses: Course[] }) {
  const internship = courses.find((c) => c.kind === "internship");
  const state = useApi<{ required_course_code: string; required_name: string; min_score: number }[]>(internship ? `/api/admin/lms/courses/${internship.code}/prerequisites` : null);
  const [required, setRequired] = useState("");
  const [min, setMin] = useState("5");
  const [open, setOpen] = useState(false);
  const add = useAction(() => {
    setRequired("");
    setOpen(false);
    state.reload();
  });
  const remove = useAction(state.reload);
  if (!internship) return null;
  return (
    <>
      <h3>Học phần tiên quyết của {internship.code} ({internship.name})</h3>
      <Async state={state}>
        {(list) =>
          list.length === 0 ? (
            <Empty>Chưa đặt tiên quyết.</Empty>
          ) : (
            <Table head={["Học phần", "Điểm tối thiểu", ""]}>
              {list.map((p) => (
                <tr key={p.required_course_code}>
                  <td>
                    {p.required_course_code} — {p.required_name}
                  </td>
                  <td>{p.min_score}</td>
                  <td>
                    <Button disabled={remove.busy} onClick={() => void remove.run(() => send("DELETE", `/api/admin/lms/courses/${internship.code}/prerequisites/${p.required_course_code}`))}>
                      Bỏ
                    </Button>
                  </td>
                </tr>
              ))}
            </Table>
          )
        }
      </Async>
      <Row>
        <Button onClick={() => setOpen(true)}>Thêm tiên quyết</Button>
      </Row>
      <FormDialog title="Thêm học phần tiên quyết" open={open} onOpenChange={setOpen}>
        <Field label="Học phần" required>
          <select value={required} onChange={(e) => setRequired(e.target.value)}>
            <option value="">Chọn học phần</option>
            {courses.filter((c) => c.code !== internship.code).map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Điểm tối thiểu">
          <input type="number" step="0.5" min={0} max={10} value={min} onChange={(e) => setMin(e.target.value)} />
        </Field>
        <ErrorText message={add.error} />
        <Row>
          <Button disabled={add.busy || !required} onClick={() => void add.run(() => send("PUT", `/api/admin/lms/courses/${internship.code}/prerequisites`, { required_course_code: required, min_score: Number(min) }))}>
            Lưu
          </Button>
          <Button onClick={() => setOpen(false)}>Hủy</Button>
        </Row>
      </FormDialog>
      <ErrorText message={remove.error} />
    </>
  );
}

function Students() {
  const state = useApi<LmsStudent[]>("/api/admin/lms/students");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"add" | "edit" | null>(null);
  const save = useAction(() => {
    setMode(null);
    state.reload();
  });
  const openAdd = () => {
    setCode("");
    setName("");
    save.clearError();
    setMode("add");
  };
  const pick = (studentCode: string) => {
    const s = state.data?.find((x) => x.student_code === studentCode);
    if (s) {
      setCode(s.student_code);
      setName(s.full_name);
    }
  };
  // Mở popup sửa với sinh viên đầu tiên chọn sẵn; đổi sinh viên bằng ô chọn có tìm kiếm (mã SV không gõ tự do).
  const openEdit = () => {
    const first = state.data?.[0];
    if (!first) return;
    pick(first.student_code);
    save.clearError();
    setMode("edit");
  };
  const editing = mode === "edit";
  return (
    <Card
      title="Sinh viên trong LMS"
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
          <Table head={["Mã SV", "Họ tên", "Tín chỉ tích lũy từ thực tập"]}>
            {list.map((s) => (
              <tr key={s.student_code}>
                <td>{s.student_code}</td>
                <td>{s.full_name}</td>
                <td>{s.credits}</td>
              </tr>
            ))}
          </Table>
        )}
      </Async>
      <FormDialog title={editing ? "Sửa sinh viên" : "Thêm sinh viên"} open={mode !== null} onOpenChange={(o) => !o && setMode(null)}>
        <Field label="Mã sinh viên" required>
          {editing ? (
            <SearchSelect options={(state.data ?? []).map((s) => ({ value: s.student_code, label: s.student_code }))} value={code} onChange={pick} placeholder="Tìm sinh viên..." />
          ) : (
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          )}
        </Field>
        <Field label="Họ tên">
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <ErrorText message={save.error} />
        <Row>
          <Button disabled={save.busy || !code.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/lms/students", { student_code: code, full_name: name }))}>
            Lưu
          </Button>
          <Button onClick={() => setMode(null)}>Hủy</Button>
        </Row>
      </FormDialog>
    </Card>
  );
}

function Grades() {
  const [form, setForm] = useState({ student_code: "", course_code: "", score: "", term: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const save = useAction(() => {
    setMsg("Đã lưu điểm.");
    setOpen(false);
  });
  const imp = useAction();
  return (
    <Card
      title="Nhập điểm"
      className="bg-background"
      actions={
        <Button
          variant="primary"
          onClick={() => {
            setForm({ student_code: "", course_code: "", score: "", term: "" });
            save.clearError();
            setOpen(true);
          }}
        >
          Thêm điểm
        </Button>
      }
    >
      <FormDialog title="Nhập điểm" open={open} onOpenChange={setOpen}>
        <Field label="Mã sinh viên" required>
          <input value={form.student_code} onChange={(e) => setForm({ ...form, student_code: e.target.value })} />
        </Field>
        <Field label="Mã học phần" required>
          <input value={form.course_code} onChange={(e) => setForm({ ...form, course_code: e.target.value })} />
        </Field>
        <Field label="Điểm" required>
          <input type="number" step="0.1" min={0} max={10} value={form.score} onChange={(e) => setForm({ ...form, score: e.target.value })} />
        </Field>
        <Field label="Học kỳ">
          <input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} />
        </Field>
        <ErrorText message={save.error} />
        <Row>
          <Button disabled={save.busy || !form.student_code || !form.course_code || form.score === ""} onClick={() => void save.run(() => send("PUT", "/api/admin/lms/grades", { ...form, score: Number(form.score) }))}>
            Lưu điểm
          </Button>
          <Button onClick={() => setOpen(false)}>Hủy</Button>
        </Row>
      </FormDialog>
      <Field label="Hoặc nhập từ CSV">
        <FilePicker
          label="Chọn tệp CSV"
          accept=".csv"
          disabled={imp.busy}
          onFile={(file) =>
            void imp.run(async () => {
              const r = await upload<{ imported: number; errors: { line: number; error: string }[] }>("/api/admin/lms/grades/import", file);
              setMsg(`Đã nhập ${r.imported} dòng.` + (r.errors.length ? ` Lỗi: ${r.errors.map((e) => `dòng ${e.line}: ${e.error}`).join("; ")}` : ""));
            })
          }
        />
      </Field>
      <ErrorText message={imp.error} />
      <OkText message={msg} />
    </Card>
  );
}
