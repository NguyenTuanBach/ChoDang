"use client";

import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import type { InternshipDetail } from "@/lib/types";
import { Async, Badge, Button, Card, Empty, ErrorText, Page, Row, StatusBadge, Table } from "@/components/ui/ui";

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

  return (
    <>
      <Card>
        <Row>
          <StatusBadge kind="internship" value={row.status} />
        </Row>
        {row.status === "in_progress" && (
          <>
            <p>
              Khi đã nộp <strong>báo cáo cuối kỳ (M4)</strong> và <strong>phiếu đánh giá có xác nhận của doanh nghiệp (M5)</strong> ở trang “Mốc & minh chứng”, bạn nộp kết thúc để giảng viên thẩm định.
            </p>
            <ErrorText message={submit.error} />
            <Button variant="primary" disabled={!ready || submit.busy} onClick={() => void submit.run(() => send("POST", "/api/student/internship/submit-for-credit"))}>
              Nộp kết thúc thực tập
            </Button>
            {!ready && <p>Chưa đủ: cần nộp mốc M4 và M5.</p>}
          </>
        )}
        {row.status === "pending_credit" && <p>Giảng viên đang thẩm định điều kiện công nhận tín chỉ. Bạn vẫn nộp bổ sung được mốc M4/M5 nếu được trả lại.</p>}
        {row.status === "credit_review" && <p>Giảng viên đã thẩm định đạt. Quản trị viên sẽ phê duyệt cuối cùng.</p>}
        {row.status === "completed" && <p>Chúc mừng! Kết quả thực tập được công nhận và đã ghi sang LMS.</p>}
        {row.status === "closed_no_credit" && <p>Đợt thực tập kết thúc, không được công nhận tín chỉ. Lý do: {row.decision_reason || "—"}</p>}
        {!["in_progress", "pending_credit", "credit_review", "completed", "closed_no_credit"].includes(row.status) && <p>Bước này mở khi bạn đang thực tập.</p>}
      </Card>

      {detail.credit && (
        <Card title="Điều kiện công nhận tín chỉ (hệ thống tính, người quyết định)">
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
        </Card>
      )}
    </>
  );
}
