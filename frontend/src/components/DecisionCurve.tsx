import { useEffect, useRef, useState } from "react";
import type { Prediction } from "../api";
import { percent, years } from "../format";

const M = { l: 42, r: 14, t: 18, b: 34 };

/** Width of an element in CSS pixels, kept up to date as it resizes. */
function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

interface Props {
  curve: Prediction["curve"];
  medianDays: number | null;
  typicalDays: number | null;
  horizonDays?: number;
}

/** Cumulative chance of a decision over time, with a hover crosshair and a table view. */
export function DecisionCurve({ curve, medianDays, typicalDays, horizonDays = 1825 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [boxRef, measured] = useWidth<HTMLDivElement>(720);
  const [hover, setHover] = useState<number | null>(null);
  // Draw at the real pixel width so text stays 12px on phones and desktops alike.
  const W = Math.max(300, measured);
  const H = W < 500 ? 240 : 300;
  const PW = W - M.l - M.r;
  const PH = H - M.t - M.b;
  const narrow = W < 500;
  const x = (day: number) => M.l + (day / horizonDays) * PW;
  const y = (p: number) => M.t + (1 - p) * PH;
  const path = curve.map((pt, i) => `${i ? "L" : "M"}${x(pt.day).toFixed(1)},${y(pt.decided).toFixed(1)}`).join("");
  const yearTicks = Array.from({ length: Math.floor(horizonDays / 365) + 1 }, (_, i) => i);
  const tickLabel = (yr: number) => (yr === 0 ? "Filed" : narrow ? `${yr}y` : `${yr} yr${yr > 1 ? "s" : ""}`);

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const box = svgRef.current!.getBoundingClientRect();
    const day = ((e.clientX - box.left) / box.width * W - M.l) / PW * horizonDays;
    if (day < 0 || day > horizonDays) return setHover(null);
    let best = 0;
    for (let i = 1; i < curve.length; i++) if (Math.abs(curve[i].day - day) < Math.abs(curve[best].day - day)) best = i;
    setHover(best);
  }

  const h = hover === null ? null : curve[hover];
  const at = (day: number) => curve.reduce((a, b) => (Math.abs(b.day - day) < Math.abs(a.day - day) ? b : a));

  return (
    <div className="chart" ref={boxRef}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Chance of a decision: ${percent(at(365).decided)} after 1 year, ${percent(at(1095).decided)} after 3 years`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <g className="axis">
          {[0, 0.25, 0.5, 0.75, 1].map((p) => (
            <g key={p}>
              <line className="gridline" x1={M.l} x2={W - M.r} y1={y(p)} y2={y(p)} />
              <text x={M.l - 8} y={y(p) + 4} textAnchor="end">{percent(p)}</text>
            </g>
          ))}
          {yearTicks.map((yr) => (
            <text key={yr} x={x(yr * 365)} y={H - M.b + 20} textAnchor="middle">
              {tickLabel(yr)}
            </text>
          ))}
        </g>

        {typicalDays !== null && typicalDays <= horizonDays && (
          <g>
            <line className="ref" x1={x(typicalDays)} x2={x(typicalDays)} y1={M.t} y2={M.t + PH} />
            <text className="lbl" x={x(typicalDays) + (typicalDays > horizonDays * 0.6 ? -6 : 6)} y={M.t + 12}
              textAnchor={typicalDays > horizonDays * 0.6 ? "end" : "start"}>
              {narrow ? "Typical court" : "Typical court's median"}
            </text>
          </g>
        )}
        {medianDays !== null && (
          <g>
            <line className="med" x1={x(medianDays)} x2={x(medianDays)} y1={y(0.5)} y2={M.t + PH} />
            <line className="med" x1={M.l} x2={x(medianDays)} y1={y(0.5)} y2={y(0.5)} />
            <text className="lbl" x={x(medianDays) + 6} y={y(0.5) + 16}>Median: {years(medianDays)}</text>
          </g>
        )}

        <path className="curve" d={path} />

        {h && (
          <g>
            <line className="cross" x1={x(h.day)} x2={x(h.day)} y1={M.t} y2={M.t + PH} />
            <circle className="dot" cx={x(h.day)} cy={y(h.decided)} r={5} />
          </g>
        )}
        <rect x={M.l} y={M.t} width={PW} height={PH} fill="transparent" />
      </svg>

      {h && (
        <div className="tip" style={{ left: `${Math.min(82, Math.max(18, (x(h.day) / W) * 100))}%`, top: `${(y(h.decided) / H) * 100}%` }}>
          After {h.day === 0 ? "filing" : years(h.day)}: <b>{percent(h.decided)}</b> decided
        </div>
      )}

      <details className="table-view">
        <summary>Show as table</summary>
        <table>
          <thead>
            <tr><th>Time since filing</th><th>Chance decided</th></tr>
          </thead>
          <tbody>
            {[30, 90, 180, 365, 730, 1095, 1460, 1825].map((d) => (
              <tr key={d}><td>{years(d)}</td><td>{percent(at(d).decided)}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
