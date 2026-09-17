/** Admin 1.1 – Stacked bar SV tương tác | không tương tác theo khoa; nhấn vào cột để drill-down (SPEC 5.2, 5.4). */
import { useMemo, useRef } from "react";
import { Bar, getElementAtEvent } from "react-chartjs-2";
import { CHROME, SERIES } from "../theme/tokens.js";
import { fmtInt, fmtPercent, share } from "../utils/format.js";
import { axis, vnNumber } from "./setup.js";

export default function EnrollmentStackedBar({ items, labelKey = "faculty_name", onSelect }) {
  const ref = useRef(null);
  const { data, options } = useMemo(() => ({
    data: {
      labels: items.map((i) => i[labelKey]),
      datasets: [
        {
          label: "Có tương tác", data: items.map((i) => i.active), backgroundColor: SERIES.blue,
          borderColor: CHROME.surface, borderWidth: { right: 2 }, borderSkipped: false, maxBarThickness: 24,
        },
        {
          label: "Không tương tác", data: items.map((i) => i.inactive), backgroundColor: CHROME.neutral,
          borderRadius: 4, borderSkipped: "start", maxBarThickness: 24,
        },
      ],
    },
    options: {
      indexAxis: "y",
      interaction: { mode: "index", axis: "y", intersect: false },
      plugins: {
        legend: { position: "top", align: "start", labels: { pointStyle: "rect" } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const item = items[ctx.dataIndex];
              return ` ${ctx.dataset.label}: ${fmtInt(ctx.parsed.x)} SV (${fmtPercent(share(ctx.parsed.x, item.enrolled))})`;
            },
            footer: (ctx) => {
              const item = items[ctx[0].dataIndex];
              return [`Đăng ký: ${fmtInt(item.enrolled)} lượt · ${fmtInt(item.red_count)} SV nguy cơ đỏ`,
                onSelect ? "Nhấn để xem các môn" : ""];
            },
          },
        },
      },
      scales: {
        x: axis({ stacked: true, beginAtZero: true, ticks: { callback: vnNumber } }),
        y: axis({ stacked: true, grid: { display: false }, ticks: { color: CHROME.ink } }),
      },
    },
  }), [items, labelKey, onSelect]);

  const handleClick = (event) => {
    if (!onSelect || !ref.current) return;
    const [element] = getElementAtEvent(ref.current, event);
    if (element) onSelect(items[element.index]);
  };

  return (
    <Bar ref={ref} data={data} options={options} onClick={handleClick} style={{ cursor: onSelect ? "pointer" : "default" }}
      role="img" aria-label="Biểu đồ sinh viên đăng ký và tương tác theo khoa" />
  );
}
