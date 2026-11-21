"use client";

import { useMemo, useState } from "react";
import { send } from "@/lib/http";
import { useAction, useApi } from "@/lib/hooks";
import { fmtDate } from "@/lib/labels";
import type { InternshipDetail } from "@/lib/types";
import { Async, Button, Card, Empty, ErrorText, Field, Page, Pre } from "@/components/ui/ui";

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function JournalPage() {
  const state = useApi<InternshipDetail>("/api/student/internship");
  return (
    <Page title="Nhật ký tuần">
      <Async state={state}>{(d) => <Content detail={d} reload={state.reload} />}</Async>
    </Page>
  );
}

function Content({ detail, reload }: { detail: InternshipDetail; reload: () => void }) {
  const row = detail.internship;
  const done = useMemo(() => new Set(detail.journals.map((j) => j.week_start)), [detail.journals]);
  // Các tuần đã bắt đầu mà chưa có nhật ký (tuần k bắt đầu ở start + 7k).
  const open = useMemo(() => {
    if (!row?.start_date) return [];
    const today = new Date().toISOString().slice(0, 10);
    const weeks: { value: string; label: string }[] = [];
    for (let k = 0; k < 40; k++) {
      const start = addDays(row.start_date, 7 * k);
      if (start > today || (row.end_date && start > row.end_date)) break;
      if (!done.has(start)) weeks.push({ value: start, label: `Tuần ${k + 1} (bắt đầu ${fmtDate(start)})` });
    }
    return weeks;
  }, [row, done]);
  const [week, setWeek] = useState("");
  const [content, setContent] = useState("");
  const submit = useAction(() => {
    setContent("");
    setWeek("");
    reload();
  });

  if (!row) return <Empty>Bạn chưa có hồ sơ thực tập.</Empty>;
  const selected = week || open[0]?.value || "";

  return (
    <>
      {row.status === "in_progress" ? (
        <Card title="Nộp nhật ký">
          {open.length === 0 ? (
            <Empty>Bạn đã nộp nhật ký cho mọi tuần đã bắt đầu.</Empty>
          ) : (
            <>
              <Field label="Tuần">
                <select value={selected} onChange={(e) => setWeek(e.target.value)}>
                  {open.map((w) => (
                    <option key={w.value} value={w.value}>
                      {w.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Công việc đã làm trong tuần" hint="Tối thiểu 20 ký tự. Nhật ký đã nộp không sửa tại chỗ.">
                <textarea value={content} onChange={(e) => setContent(e.target.value)} />
              </Field>
              <ErrorText message={submit.error} />
              <Button variant="primary" disabled={submit.busy || content.trim().length < 20 || !selected} onClick={() => void submit.run(() => send("POST", "/api/student/journal", { week_start: selected, content }))}>
                Nộp nhật ký
              </Button>
            </>
          )}
        </Card>
      ) : (
        <Card>
          <p>Bạn nộp được nhật ký khi hồ sơ ở trạng thái “Đang thực tập”.</p>
        </Card>
      )}
      <Card title="Nhật ký đã nộp">
        {detail.journals.length === 0 && <Empty>Chưa có nhật ký.</Empty>}
        {detail.journals.map((j) => (
          <div key={j.id} style={{ marginBottom: "1rem" }}>
            <strong>Tuần bắt đầu {fmtDate(j.week_start)}</strong>
            <Pre>{j.content}</Pre>
            {j.lecturer_comment && <p>Nhận xét của giảng viên: {j.lecturer_comment}</p>}
          </div>
        ))}
      </Card>
    </>
  );
}
