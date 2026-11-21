"use client";

import { useState } from "react";
import { send, upload } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import type { Course, LmsStudent, SyncJob } from "@/lib/types";
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
    <Card title="Đồng bộ kết quả quy đổi sang LMS">
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
  const save = useAction(() => {
    setForm({ code: "", name: "", credits: "3", kind: "regular" });
    state.reload();
  });
  return (
    <Card title="Học phần">
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
      <Row>
        <input placeholder="Mã" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} size={8} />
        <input placeholder="Tên học phần" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} size={30} />
        <input type="number" min={1} value={form.credits} onChange={(e) => setForm({ ...form, credits: e.target.value })} style={{ width: "4rem" }} />
        <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          <option value="regular">Thường</option>
          <option value="internship">Thực tập</option>
        </select>
        <Button variant="primary" disabled={save.busy || !form.code.trim() || !form.name.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/lms/courses", { ...form, credits: Number(form.credits) }))}>
          Thêm / sửa
        </Button>
      </Row>
      <ErrorText message={save.error} />
      <Prerequisites courses={state.data ?? []} />
    </Card>
  );
}

function Prerequisites({ courses }: { courses: Course[] }) {
  const internship = courses.find((c) => c.kind === "internship");
  const state = useApi<{ required_course_code: string; required_name: string; min_score: number }[]>(internship ? `/api/admin/lms/courses/${internship.code}/prerequisites` : null);
  const [required, setRequired] = useState("");
  const [min, setMin] = useState("5");
  const add = useAction(state.reload);
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
        <select value={required} onChange={(e) => setRequired(e.target.value)}>
          <option value="">Chọn học phần</option>
          {courses.filter((c) => c.code !== internship.code).map((c) => (
            <option key={c.code} value={c.code}>
              {c.code} — {c.name}
            </option>
          ))}
        </select>
        <input type="number" step="0.5" min={0} max={10} value={min} onChange={(e) => setMin(e.target.value)} style={{ width: "4rem" }} />
        <Button disabled={add.busy || !required} onClick={() => void add.run(() => send("PUT", `/api/admin/lms/courses/${internship.code}/prerequisites`, { required_course_code: required, min_score: Number(min) }))}>
          Thêm tiên quyết
        </Button>
      </Row>
      <ErrorText message={add.error ?? remove.error} />
    </>
  );
}

function Students() {
  const state = useApi<LmsStudent[]>("/api/admin/lms/students");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const save = useAction(() => {
    setCode("");
    setName("");
    state.reload();
  });
  return (
    <Card title="Sinh viên trong LMS">
      <p>
        <small>Mã sinh viên ở đây phải trùng mã sinh viên đã đặt trong tài khoản để ghi kết quả quy đổi tín chỉ.</small>
      </p>
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
      <Row>
        <input placeholder="Mã SV" value={code} onChange={(e) => setCode(e.target.value)} size={10} />
        <input placeholder="Họ tên" value={name} onChange={(e) => setName(e.target.value)} size={30} />
        <Button variant="primary" disabled={save.busy || !code.trim()} onClick={() => void save.run(() => send("PUT", "/api/admin/lms/students", { student_code: code, full_name: name }))}>
          Thêm / sửa
        </Button>
      </Row>
      <ErrorText message={save.error} />
    </Card>
  );
}

function Grades() {
  const [form, setForm] = useState({ student_code: "", course_code: "", score: "", term: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const save = useAction(() => setMsg("Đã lưu điểm."));
  const imp = useAction();
  return (
    <Card title="Nhập điểm">
      <Row>
        <input placeholder="Mã SV" value={form.student_code} onChange={(e) => setForm({ ...form, student_code: e.target.value })} size={10} />
        <input placeholder="Mã học phần" value={form.course_code} onChange={(e) => setForm({ ...form, course_code: e.target.value })} size={10} />
        <input type="number" step="0.1" min={0} max={10} placeholder="Điểm" value={form.score} onChange={(e) => setForm({ ...form, score: e.target.value })} style={{ width: "5rem" }} />
        <input placeholder="Học kỳ" value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} size={10} />
        <Button variant="primary" disabled={save.busy || !form.student_code || !form.course_code || form.score === ""} onClick={() => void save.run(() => send("PUT", "/api/admin/lms/grades", { ...form, score: Number(form.score) }))}>
          Lưu điểm
        </Button>
      </Row>
      <ErrorText message={save.error} />
      <Field label="Hoặc nhập từ CSV" hint="Cột: student_code, course_code, score, term (tùy chọn)">
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
