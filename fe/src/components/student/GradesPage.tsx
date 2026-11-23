"use client";

import { useApi } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/labels";
import type { LmsRecord } from "@/lib/types";
import { Async, Badge, Card, Empty, Page, Table } from "@/components/ui/ui";

// Thứ tự: tín chỉ nhận được từ thực tập (quan trọng nhất) → điều kiện để học học phần thực tập → bảng điểm các môn đã học.
export function RecordView({ data }: { data: LmsRecord }) {
  const record = data.record;
  return (
    <>
      <Card title="Tín chỉ từ thực tập">
        {!record ? (
          <Empty>{data.student_code ? `Chưa có dữ liệu trong LMS cho mã ${data.student_code}.` : "Tài khoản chưa có mã sinh viên."}</Empty>
        ) : (
          <>
            <p className="m-0 flex items-baseline gap-2">
              <span className="text-4xl font-bold tabular-nums">{record.total_credits}</span>
              <span className="text-sm text-muted-foreground">tín chỉ đã được công nhận từ thực tập</span>
            </p>
            {record.credits.length === 0 ? (
              <div className="mt-4">
                <Empty>Chưa có tín chỉ thực tập được ghi vào LMS.</Empty>
              </div>
            ) : (
              <div className="mt-4">
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
              </div>
            )}
          </>
        )}
      </Card>

      <Card title="Điều kiện để học học phần thực tập">
        <p className="m-0 mb-3 text-sm text-muted-foreground">Cần học xong và đạt điểm tối thiểu ở một số môn trước khi được thực tập.</p>
        <Badge tone={data.prerequisites.met ? "good" : "warn"}>{data.prerequisites.met ? "Đủ điều kiện" : "Chưa đủ điều kiện"}</Badge>
        {data.prerequisites.missing.length > 0 && (
          <ul className="mb-0 mt-3">
            {data.prerequisites.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        )}
      </Card>

      {record && (
        <Card title={`Bảng điểm các môn đã học — ${record.student_code} (${record.full_name})`}>
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
      )}
    </>
  );
}

export default function GradesPage() {
  const state = useApi<LmsRecord>("/api/lms/me");
  return (
    <Page title="Tín chỉ và bảng điểm">
      <Async state={state}>{(d) => <RecordView data={d} />}</Async>
    </Page>
  );
}
