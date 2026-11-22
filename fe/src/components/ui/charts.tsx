// Biểu đồ nhẹ viết bằng SVG/CSS (không thêm thư viện): tròn (donut) và cột.

export type ChartDatum = { label: string; value: number; color: string };

// Màu phân loại cho biểu đồ tròn (mỗi trạng thái một màu, dễ phân biệt).
export const CATEGORY_COLORS = ["#16a34a", "#dc2626", "#f59e0b", "#2563eb", "#7c3aed", "#0d9488", "#db2777", "#737373"];

export function PieChart({ data }: { data: ChartDatum[] }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) return <p className="m-0 text-sm text-muted-foreground">Chưa có dữ liệu.</p>;
  // Vị trí bắt đầu của từng lát (theo % chu vi), tính trước để render không phải gán lại biến.
  const slices = data.map((d, i) => ({ ...d, pct: (d.value / total) * 100, start: (data.slice(0, i).reduce((s, x) => s + x.value, 0) / total) * 100 }));
  return (
    <div className="flex h-full min-h-60 flex-col items-center justify-center gap-6 sm:flex-row">
      <svg viewBox="0 0 42 42" className="size-52 shrink-0" role="img" aria-label="Biểu đồ tròn">
        <g transform="rotate(-90 21 21)">
          <circle cx="21" cy="21" r="15.9155" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted" />
          {slices
            .filter((d) => d.value > 0)
            .map((d) => (
              <circle key={d.label} cx="21" cy="21" r="15.9155" fill="none" stroke={d.color} strokeWidth="6" strokeDasharray={`${d.pct} ${100 - d.pct}`} strokeDashoffset={-d.start}>
                <title>{`${d.label}: ${d.value}`}</title>
              </circle>
            ))}
        </g>
        <text x="21" y="21" textAnchor="middle" dominantBaseline="central" className="fill-foreground text-[7px] font-bold">
          {total}
        </text>
      </svg>
      <ul className="m-0 grid w-full list-none gap-2 p-0 text-sm">
        {data.map((d) => (
          <li key={d.label} className="flex items-center gap-2">
            <span aria-hidden="true" className="size-3 shrink-0 rounded-full" style={{ backgroundColor: d.color }} />
            <span className="min-w-0 flex-1">{d.label}</span>
            <strong className="tabular-nums">{d.value}</strong>
            <span className="w-12 text-right tabular-nums text-muted-foreground">{Math.round((d.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BarChart({ data }: { data: ChartDatum[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (data.length === 0) return <p className="m-0 text-sm text-muted-foreground">Chưa có dữ liệu.</p>;
  return (
    <div className="flex h-56 items-end gap-4 border-b-2 border-foreground/25 px-2" role="img" aria-label="Biểu đồ cột">
      {data.map((d) => (
        <div key={d.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
          <span className="text-sm font-bold tabular-nums">{d.value}</span>
          <div className="w-full max-w-14 rounded-t-md" style={{ height: `${(d.value / max) * 75}%`, minHeight: d.value > 0 ? 4 : 0, backgroundColor: d.color }} title={`${d.label}: ${d.value}`} />
        </div>
      ))}
    </div>
  );
}

// Nhãn dưới trục cột: tách khỏi vùng vẽ để cột sát đường nền, nhãn dài tự xuống dòng.
export function BarLabels({ data }: { data: ChartDatum[] }) {
  return (
    <div className="flex gap-4 px-2 pt-2">
      {data.map((d) => (
        <span key={d.label} className="min-w-0 flex-1 text-center text-xs text-muted-foreground">
          {d.label}
        </span>
      ))}
    </div>
  );
}
