/** Admin 1.2 – Heatmap giờ × thứ (chartjs-chart-matrix): thang tuần tự một màu xanh, nhạt = ít, đậm = nhiều. */
import { useMemo } from "react";
import { Chart } from "react-chartjs-2";
import { CHROME, SEQUENTIAL_BLUE } from "../theme/tokens.js";
import { DOW_LABELS, fmtDecimal, fmtInt } from "../utils/format.js";

const HOURS = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0"));
const DAYS = DOW_LABELS.slice(1);

export default function TrafficHeatmap({ matrix }) {
  const { data, options, min, max } = useMemo(() => {
    const values = matrix.map((c) => Number(c.avg_requests));
    const lo = values.length ? Math.min(...values) : 0;
    const hi = values.length ? Math.max(...values) : 0;
    const colorOf = (v) => {
      if (hi === lo) return SEQUENTIAL_BLUE[6];
      const step = Math.floor(((v - lo) / (hi - lo)) * (SEQUENTIAL_BLUE.length - 1));
      return SEQUENTIAL_BLUE[Math.max(0, Math.min(SEQUENTIAL_BLUE.length - 1, step))];
    };
    return {
      min: lo,
      max: hi,
      data: {
        datasets: [{
          label: "Requests trung bình / giờ",
          data: matrix.map((c) => ({ x: HOURS[c.hour_of_day], y: DAYS[c.day_of_week - 1], v: Number(c.avg_requests), cell: c })),
          backgroundColor: (ctx) => colorOf(ctx.raw?.v ?? lo),
          borderColor: CHROME.surface,
          borderWidth: 1,
          hoverBorderColor: CHROME.ink,
          hoverBorderWidth: 2,
          width: ({ chart }) => Math.max(0, (chart.chartArea?.width ?? 0) / 24 - 2),
          height: ({ chart }) => Math.max(0, (chart.chartArea?.height ?? 0) / 7 - 2),
        }],
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => `${items[0].raw.y}, ${items[0].raw.x}:00`,
              label: (item) => [
                ` Trung bình ${fmtInt(item.raw.v)} requests/giờ`,
                ` Online trung bình ${fmtDecimal(item.raw.cell.avg_online_users, 1)}`,
                ` Là giờ cao điểm ở ${fmtDecimal(item.raw.cell.peak_share, 0)}% số ngày`,
              ],
            },
          },
        },
        scales: {
          x: {
            type: "category", labels: HOURS, offset: true, grid: { display: false }, border: { display: false },
            ticks: { color: CHROME.muted, maxRotation: 0, autoSkip: false, callback: (_, i) => (i % 2 === 0 ? `${HOURS[i]}h` : "") },
          },
          y: { type: "category", labels: DAYS, offset: true, grid: { display: false }, border: { display: false }, ticks: { color: CHROME.secondary } },
        },
      },
    };
  }, [matrix]);

  return (
    <>
      <div className="chart-box" style={{ height: 300 }}>
        <Chart type="matrix" data={data} options={options} role="img" aria-label="Heatmap lưu lượng theo giờ và thứ" />
      </div>
      <div className="heat-scale" style={{ marginTop: 8 }}>
        <span>Ít: {fmtInt(min)}</span>
        <span className="heat-scale-bar" style={{ background: `linear-gradient(90deg, ${SEQUENTIAL_BLUE.join(", ")})` }} />
        <span>Nhiều: {fmtInt(max)} requests TB/giờ</span>
      </div>
    </>
  );
}

export const heatmapTableColumns = [
  { title: "Thứ", dataIndex: "day_of_week", render: (d) => DAYS[d - 1], sorter: (a, b) => a.day_of_week - b.day_of_week },
  { title: "Giờ", dataIndex: "hour_of_day", render: (h) => `${HOURS[h]}:00`, sorter: (a, b) => a.hour_of_day - b.hour_of_day },
  { title: "Requests TB", dataIndex: "avg_requests", align: "right", render: fmtInt, defaultSortOrder: "descend", sorter: (a, b) => a.avg_requests - b.avg_requests },
  { title: "Online TB", dataIndex: "avg_online_users", align: "right", render: (v) => fmtDecimal(v, 1) },
  { title: "% ngày là giờ cao điểm", dataIndex: "peak_share", align: "right", render: (v) => `${fmtDecimal(v, 0)}%` },
];
