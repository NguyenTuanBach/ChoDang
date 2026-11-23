"use client";

import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import type { InternshipDetail } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Page, StatusBadge, Table } from "@/components/ui/ui";

export default function FinalPage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Kết thúc thực tập và công nhận tín chỉ">
      <Async state={state}>{(d) => <Content detail={d} reload={state.reload} />}</Async>
    </Page>
  );
}

function Content({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const submit = useAction(reload);
  const row = detail.internship;
  if (!row) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;
  const by = Object.fromEntries(detail.milestones.map((m) => [m.code, m]));
  const ready = ["M4", "M5"].every((c) => by[c] && ["submitted", "accepted"].includes(by[c].stored_status));

  const requirements = [
    { code: "M4", label: "Báo cáo cuối kỳ" },
    { code: "M5", label: "Phiếu đánh giá của doanh nghiệp" },
  ].map((r) => ({ ...r, done: !!by[r.code] && ["submitted", "accepted"].includes(by[r.code].stored_status) }));
  const message: Record<string, string> = {
    in_progress: "Khi đã nộp M4 và M5, bạn nộp kết thúc để giảng viên thẩm định.",
    pending_credit: "Giảng viên đang thẩm định. Nếu được trả lại, bạn nộp bổ sung M4/M5.",
    credit_review: "Giảng viên đã thẩm định đạt. Quản trị viên sẽ phê duyệt cuối cùng.",
    completed: "Kết quả thực tập được công nhận và đã ghi sang LMS.",
    closed_no_credit: `Đợt thực tập kết thúc, không được công nhận tín chỉ. Lý do: ${row.decision_reason || "—"}`,
  };
  const met = detail.credit ? detail.credit.items.filter((i) => i.met).length : 0;

  return (
    <>
      <Card title="Kết thúc thực tập">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
            <StatusBadge kind="internship" value={row.status} />
            <p className="m-0 text-sm">{message[row.status] ?? "Bước này mở khi bạn đang thực tập."}</p>
          </div>
          {row.status === "in_progress" && (
            <Button variant="primary" disabled={!ready || submit.busy} onClick={() => void submit.run(() => send("POST", "/api/student/internship/submit-for-credit"))}>
              Nộp kết thúc thực tập
            </Button>
          )}
        </div>
        {row.status === "in_progress" && (
          <div className="mt-4 grid grid-cols-1 gap-3 border-t border-foreground/15 pt-4 sm:grid-cols-2">
            {requirements.map((r) => (
              <div key={r.code} className="flex items-center justify-between gap-3 rounded-lg border-2 border-foreground/15 bg-background px-3 py-2 text-sm">
                <span>
                  <strong>{r.code}</strong> · {r.label}
                </span>
                <Badge tone={r.done ? "good" : "warn"}>{r.done ? "Đã nộp" : "Chưa nộp"}</Badge>
              </div>
            ))}
          </div>
        )}
        <ErrorText message={submit.error} />
      </Card>

      {detail.credit && (
        <Card title="Điều kiện công nhận tín chỉ" actions={<span className="text-sm text-muted-foreground">Đạt {met}/{detail.credit.items.length} điều kiện</span>}>
          <Table head={["Mã", "Điều kiện", "Hiện tại", "Ngưỡng", "Kết quả"]}>
            {detail.credit.items.map((i) => (
              <tr key={i.code}>
                <td>{i.code}</td>
                <td>{i.label}</td>
                <td>{i.value}</td>
                <td>{i.threshold}</td>
                <td>
                  <Badge tone={i.met ? "good" : "warn"}>{i.met ? "Đạt" : "Chưa đạt"}</Badge>
                </td>
              </tr>
            ))}
          </Table>
          <p className="mb-0 mt-3 text-xs text-muted-foreground">Hệ thống chỉ tính đạt/chưa đạt; giảng viên thẩm định và quản trị viên phê duyệt quyết định công nhận.</p>
        </Card>
      )}
    </>
  );
}
