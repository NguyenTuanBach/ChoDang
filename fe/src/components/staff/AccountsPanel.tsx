"use client";

import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { ACCOUNT_STATUS } from "@/lib/labels";
import type { Account } from "@/lib/types";
import { Async, Button, Card, Empty, ErrorText, Field, OkText, Page, Row, StatusBadge, Table } from "@/components/ui/ui";

type Props = { viewer: "admin" | "lecturer"; role: "lecturer" | "student"; title: string };

// Mời tài khoản qua email (QTV mời GV, GV/QTV mời SV), xem trạng thái lời mời, thu hồi / mời lại, mã sinh viên, giảng viên phụ trách.
export default function AccountsPanel({ viewer, role, title }: Props) {
  const accounts = useApi<Account[]>("/api/invitations");
  const lecturers = useApi<Account[]>(viewer === "admin" && role === "student" ? "/api/lecturers" : null);
  return (
    <Page title={title}>
      <InviteForm viewer={viewer} role={role} lecturers={lecturers.data ?? []} onDone={accounts.reload} />
      <Card title="Danh sách">
        <Async state={accounts}>
          {(all) => {
            const list = all.filter((a) => a.role === role);
            return list.length === 0 ? (
              <Empty>Chưa có tài khoản nào.</Empty>
            ) : (
              <Table head={role === "student" ? ["Email", "Họ tên", "Mã SV", "Giảng viên", "Trạng thái", ""] : ["Email", "Họ tên", "Trạng thái", ""]}>
                {list.map((a) => (
                  <AccountRow key={a.id} account={a} viewer={viewer} lecturers={lecturers.data ?? []} reload={accounts.reload} />
                ))}
              </Table>
            );
          }}
        </Async>
      </Card>
    </Page>
  );
}

function InviteForm({ viewer, role, lecturers, onDone }: { viewer: string; role: string; lecturers: Account[]; onDone: () => void }) {
  const [text, setText] = useState("");
  const [lecturerId, setLecturerId] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const action = useAction(onDone);

  function parse() {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [email, full_name, student_code] = line.split(/[,;\t]/).map((p) => p.trim());
        return { email, full_name: full_name ?? "", student_code: student_code || null };
      });
  }

  async function invite() {
    setResult(null);
    await action.run(async () => {
      const response = await send<{ invited: Account[]; errors: { email: string; error: string }[] }>("POST", "/api/invitations", {
        role,
        items: parse(),
        lecturer_id: lecturerId ? Number(lecturerId) : null,
      });
      setResult(`Đã mời ${response.invited.length} tài khoản.` + (response.errors.length ? ` Lỗi: ${response.errors.map((e) => `${e.email} (${e.error})`).join("; ")}` : ""));
      setText("");
    });
  }

  return (
    <Card title={role === "lecturer" ? "Mời giảng viên" : "Mời sinh viên"}>
      <Field label="Danh sách email (mỗi dòng một người)" hint={role === "student" ? "Có thể thêm họ tên và mã sinh viên: email, họ tên, mã SV. Sinh viên đăng nhập bằng đúng email được mời." : "Có thể thêm họ tên: email, họ tên."}>
        <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={role === "student" ? "sv1@truong.edu.vn, Nguyễn Văn A, SV0010" : "gv1@truong.edu.vn, Cô Lan"} />
      </Field>
      {viewer === "admin" && role === "student" && (
        <Field label="Giảng viên phụ trách">
          <select value={lecturerId} onChange={(e) => setLecturerId(e.target.value)}>
            <option value="">Chưa phân công</option>
            {lecturers.map((l) => (
              <option key={l.id} value={l.id}>
                {l.full_name || l.email}
              </option>
            ))}
          </select>
        </Field>
      )}
      <ErrorText message={action.error} />
      <OkText message={result} />
      <Button variant="primary" disabled={action.busy || !text.trim()} onClick={() => void invite()}>
        Gửi lời mời
      </Button>
    </Card>
  );
}

function AccountRow({ account: a, viewer, lecturers, reload }: { account: Account; viewer: string; lecturers: Account[]; reload: () => void }) {
  const action = useAction(reload);
  const [code, setCode] = useState(a.student_code ?? "");
  return (
    <tr>
      <td>{a.email}</td>
      <td>{a.full_name}</td>
      {a.role === "student" && (
        <>
          <td>
            <Row>
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Mã SV" size={9} />
              <Button disabled={action.busy || !code.trim() || code === (a.student_code ?? "")} onClick={() => void action.run(() => send("PUT", `/api/students/${a.id}/code`, { student_code: code }))}>
                Lưu
              </Button>
            </Row>
          </td>
          <td>
            {viewer === "admin" ? (
              <select value={a.advisor_id ?? ""} onChange={(e) => e.target.value && void action.run(() => send("PUT", `/api/students/${a.id}/advisor`, { lecturer_id: Number(e.target.value) }))}>
                <option value="">Chưa phân công</option>
                {lecturers.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.full_name || l.email}
                  </option>
                ))}
              </select>
            ) : (
              "Tôi"
            )}
          </td>
        </>
      )}
      <td>
        <StatusBadge kind="raw" value={ACCOUNT_STATUS[a.status] ?? a.status} />
      </td>
      <td>
        <Row>
          {a.status !== "revoked" && (
            <Button disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/invitations/${a.id}/revoke`, { reason: a.status === "invited" ? "Thu hồi lời mời" : "Khóa tài khoản" }))}>
              {a.status === "invited" ? "Thu hồi lời mời" : "Khóa"}
            </Button>
          )}
          {(a.status === "revoked" || a.status === "invited") && (
            <Button disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/invitations/${a.id}/reinvite`))}>
              Mời lại
            </Button>
          )}
        </Row>
        <ErrorText message={action.error} />
      </td>
    </tr>
  );
}
