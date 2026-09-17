/** GV 2.1 – Doughnut tỷ lệ rủi ro; nhấn lát cắt hoặc dòng chú thích để lọc bảng (SPEC 5.3). */
import { useMemo, useRef } from "react";
import { Doughnut, getElementAtEvent } from "react-chartjs-2";
import { CRITERIA, RISK, RISK_LEVELS } from "../theme/tokens.js";
import { fmtInt, fmtPercent, share } from "../utils/format.js";

export default function RiskDoughnut({ summary, selectedLevels, onToggleLevel, criterion, onCriterion }) {
  const ref = useRef(null);
  const counts = RISK_LEVELS.map((l) => summary[l.toLowerCase()]);
  const { total } = summary;

  const { data, options } = useMemo(() => ({
    data: {
      labels: RISK_LEVELS.map((l) => RISK[l].label),
      datasets: [{
        data: counts,
        backgroundColor: RISK_LEVELS.map((l) => (selectedLevels.length && !selectedLevels.includes(l) ? RISK[l].tint : RISK[l].color)),
        borderColor: "#ffffff", borderWidth: 2, hoverOffset: 6,
      }],
    },
    options: {
      cutout: "62%",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${RISK[RISK_LEVELS[ctx.dataIndex]].icon} ${ctx.label}: ${fmtInt(ctx.parsed)} SV (${fmtPercent(share(ctx.parsed, total))})`,
          },
        },
      },
    },
  }), [counts.join(","), selectedLevels.join(","), total]); // eslint-disable-line react-hooks/exhaustive-deps

  const onClick = (event) => {
    const [element] = getElementAtEvent(ref.current, event);
    if (element) onToggleLevel(RISK_LEVELS[element.index]);
  };

  return (
    <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
      <div style={{ position: "relative", width: 176, height: 176, flex: "none" }}>
        <Doughnut ref={ref} data={data} options={options} onClick={onClick} style={{ cursor: "pointer" }}
          role="img" aria-label="Biểu đồ tỷ lệ sinh viên theo mức rủi ro" />
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none", textAlign: "center" }}>
          <div>
            <div style={{ fontSize: 26, fontWeight: 650 }}>{fmtInt(total)}</div>
            <div className="muted" style={{ fontSize: 12 }}>sinh viên</div>
          </div>
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 200 }}>
        {RISK_LEVELS.map((level, i) => {
          const active = selectedLevels.includes(level);
          return (
            <button type="button" key={level} onClick={() => onToggleLevel(level)} aria-pressed={active}
              style={{
                display: "flex", width: "100%", justifyContent: "space-between", gap: 12, padding: "6px 8px", border: 0,
                borderRadius: 6, background: active ? RISK[level].tint : "transparent", cursor: "pointer", font: "inherit", color: "inherit",
              }}>
              <span><span style={{ color: RISK[level].color }} aria-hidden>{RISK[level].icon}</span> {RISK[level].label}</span>
              <span className="tabular"><b>{fmtInt(counts[i])}</b> <span className="muted">({fmtPercent(share(counts[i], total), 0)})</span></span>
            </button>
          );
        })}
        <div className="muted" style={{ fontSize: 12, marginTop: 10, marginBottom: 4 }}>Theo tiêu chí (nhấn để lọc):</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Object.entries(CRITERIA).map(([key, label]) => (
            <button type="button" key={key} onClick={() => onCriterion(criterion === key ? undefined : key)} aria-pressed={criterion === key}
              style={{
                border: "1px solid #d9d9d9", borderRadius: 999, padding: "2px 10px", cursor: "pointer", font: "inherit", fontSize: 12,
                background: criterion === key ? "#1f2937" : "#fff", color: criterion === key ? "#fff" : "inherit",
              }}>
              {label} <b>{fmtInt(summary.by_criterion[key])}</b>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
