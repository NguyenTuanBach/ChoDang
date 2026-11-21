"use client";

import { useApi } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/labels";
import type { LmsRecord } from "@/lib/types";
import { Async, Badge, Card, Empty, Page, Table } from "@/components/ui/ui";

export function RecordView({ data }: { data: LmsRecord }) {
  const record = data.record;
  return (
    <>
      <Card title="Điều kiện tiên quyết học phần thực tập">
        <Badge tone={data.prerequisites.met ? "good" : "warn"}>{data.prerequisites.met ? "Đủ điều kiện" : "Chưa đủ điều kiện"}</Badge>
        {data.prerequisites.missing.length > 0 && (
          <ul>
            {data.prerequisites.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        )}
      </Card>
      {!record ? (
        <Card>
          <Empty>{data.student_code ? `Chưa có dữ liệu trong LMS cho mã ${data.student_code}.` : "Tài khoản chưa có mã sinh viên."}</Empty>
        </Card>
      ) : (
        <>
          <Card title={`Bảng điểm — ${record.student_code} (${record.full_name})`}>
            {record.grades.length === 0 ? (
              <Empty>Chưa có điểm.</Empty>
            ) : (
              <Table head={["Học phần", "Tên", "Tín chỉ", "Điểm", "Học kỳ"]}>
                {record.grades.map((g) => (
                  <tr key={g.course_code}>
                    <td>{g.course_code}</td>
                    <td>{g.course_name}</td>
                    <td>{g.credits}</td>
                    <td>{g.score}</td>
                    <td>{g.term}</td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
          <Card title={`Tín chỉ tích lũy quy đổi từ thực tập: ${record.total_credits}`}>
            {record.credits.length === 0 ? (
              <Empty>Chưa có tín chỉ thực tập được ghi vào LMS.</Empty>
            ) : (
              <Table head={["Học phần", "Tên", "Tín chỉ", "Nguồn", "Ghi lúc"]}>
                {record.credits.map((c) => (
                  <tr key={`${c.course_code}-${c.posted_at}`}>
                    <td>{c.course_code}</td>
                    <td>{c.course_name}</td>
                    <td>{c.credits}</td>
                    <td>{c.source}</td>
                    <td>{fmtDateTime(c.posted_at)}</td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
        </>
      )}
    </>
  );
}

export default function GradesPage() {
  const state = useApi<LmsRecord>("/api/lms/me");
  return (
    <Page title="Bảng điểm và tín chỉ (LMS)">
      <Async state={state}>{(d) => <RecordView data={d} />}</Async>
    </Page>
  );
}
