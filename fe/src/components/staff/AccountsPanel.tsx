"use client";

import { useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { ACCOUNT_STATUS } from "@/lib/labels";
import type { Account } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Field, OkText, Page, type Tone, Table } from "@/components/ui/ui";

// Đang hoạt động = xanh lá; đã mời, chưa đăng nhập (còn hạn 3 giờ) = vàng (chờ); đã thu hồi/khóa hoặc lời mời hết hạn = đỏ.
const ACCOUNT_TONE: Record<string, Tone> = { active: "good", invited: "warn", revoked: "bad" };

type Props = { viewer: "admin" | "lecturer"; role: "lecturer" | "student"; title: string };

// Mời tài khoản qua email (QTV mời GV, GV/QTV mời SV), xem trạng thái lời mời, thu hồi / mời lại, mã sinh viên, giảng viên phụ trách.
export default function AccountsPanel({ viewer, role, title }: Props) {
  const accounts = useApi<Account[]>("/api/invitations");
  const lecturers = useApi<Account[]>(viewer === "admin" && role === "student" ? "/api/lecturers" : null);
  // Mã SV sửa trực tiếp trong bảng; nút "Lưu" ở tiêu đề card lưu một lượt mọi dòng đã đổi.
  const [codes, setCodes] = useState<Record<number, string>>({});
  const changed = (accounts.data ?? []).filter((a) => a.role === "student" && codes[a.id] !== undefined && codes[a.id].trim() !== "" && codes[a.id] !== (a.student_code ?? ""));
  const saveCodes = useAction(() => {
    setCodes({});
    accounts.reload();
  });
  return (
    <Page title={title}>
      <InviteForm viewer={viewer} role={role} lecturers={lecturers.data ?? []} onDone={accounts.reload} />
      <Card
        title="Danh sách"
        className="bg-background"
        actions={
          role === "student" ? (
            <Button
              variant="primary"
              disabled={saveCodes.busy || changed.length === 0}
              onClick={() =>
                void saveCodes.run(async () => {
                  for (const a of changed) await send("PUT", `/api/students/${a.id}/code`, { student_code: codes[a.id] });
                })
              }
            >
              Lưu
            </Button>
          ) : undefined
        }
      >
        <Async state={accounts}>
          {(all) => {
            const list = all.filter((a) => a.role === role);
            return list.length === 0 ? (
              <Empty>Chưa có tài khoản nào.</Empty>
            ) : (
              <Table head={role === "student" ? ["Email", "Họ tên", "Mã SV", "Giảng viên", "Trạng thái", ""] : ["Email", "Họ tên", "Trạng thái", ""]}>
                {list.map((a) => (
                  <AccountRow key={a.id} account={a} viewer={viewer} lecturers={lecturers.data ?? []} reload={accounts.reload} code={codes[a.id] ?? a.student_code ?? ""} onCode={(v) => setCodes((c) => ({ ...c, [a.id]: v }))} />
                ))}
              </Table>
            );
          }}
        </Async>
        <ErrorText message={saveCodes.error} />
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

  // QTV mời sinh viên thì bắt buộc chọn giảng viên phụ trách (giảng viên mời thì tự là người phụ trách).
  const needsAdvisor = viewer === "admin" && role === "student";

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
    <Card
      title={role === "lecturer" ? "Mời giảng viên" : "Mời sinh viên"}
      className="bg-background"
      actions={
        <Button variant="primary" disabled={action.busy || !text.trim() || (needsAdvisor && !lecturerId)} onClick={() => void invite()}>
          Gửi lời mời
        </Button>
      }
    >
      <Field label="Danh sách email (mỗi dòng một người)" required hint={role === "student" ? "Có thể thêm họ tên và mã sinh viên: email, họ tên, mã SV. Sinh viên đăng nhập bằng đúng email được mời." : "Có thể thêm họ tên: email, họ tên."}>
        <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={role === "student" ? "sv1@truong.edu.vn, Nguyễn Văn A, SV0010" : "gv1@truong.edu.vn, Cô Lan"} />
      </Field>
      {viewer === "admin" && role === "student" && (
        <Field label="Giảng viên phụ trách" required>
          <select value={lecturerId} onChange={(e) => setLecturerId(e.target.value)}>
            <option value="" disabled>
              Chọn giảng viên
            </option>
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
    </Card>
  );
}

function AccountRow({ account: a, viewer, lecturers, reload, code, onCode }: { account: Account; viewer: string; lecturers: Account[]; reload: () => void; code: string; onCode: (value: string) => void }) {
  const action = useAction(reload);
  // Lời mời có hạn 3 giờ: còn hạn thì được thu hồi; quá hạn thì hiện "Từ chối" (đỏ) và chỉ còn nút "Mời lại".
  const expired = a.status === "invited" && a.invitation_expired;
  return (
    <tr>
      <td>{a.email}</td>
      <td>{a.full_name}</td>
      {a.role === "student" && (
        <>
          <td>
            <input className="w-28" value={code} onChange={(e) => onCode(e.target.value)} placeholder="Mã SV" />
          </td>
          <td>
            {viewer === "admin" ? (
              <select value={a.advisor_id ?? ""} onChange={(e) => e.target.value && void action.run(() => send("PUT", `/api/students/${a.id}/advisor`, { lecturer_id: Number(e.target.value) }))}>
                {a.advisor_id == null && (
                  <option value="" disabled>
                    Chọn giảng viên
                  </option>
                )}
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
        {expired ? <Badge tone="bad">Từ chối (hết hạn lời mời)</Badge> : <Badge tone={ACCOUNT_TONE[a.status] ?? "neutral"}>{ACCOUNT_STATUS[a.status] ?? a.status}</Badge>}
      </td>
      <td>
        <div className="flex flex-nowrap items-center gap-2">
          {a.status !== "revoked" && !expired && (
            <Button disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/invitations/${a.id}/revoke`, { reason: a.status === "invited" ? "Thu hồi lời mời" : "Khóa tài khoản" }))}>
              {a.status === "invited" ? "Thu hồi lời mời" : "Khóa"}
            </Button>
          )}
          {(a.status === "revoked" || expired) && (
            <Button disabled={action.busy} onClick={() => void action.run(() => send("POST", `/api/invitations/${a.id}/reinvite`))}>
              Mời lại
            </Button>
          )}
        </div>
        <ErrorText message={action.error} />
      </td>
    </tr>
  );
}
