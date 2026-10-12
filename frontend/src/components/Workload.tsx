import type { Prediction } from "../api";
import { percent } from "../format";

/** The court's congestion figures as of the snapshot date. */
export function Workload({ p }: { p: Prediction }) {
  const c = p.congestion;
  const rows: [string, string][] = [
    ["Court", p.court.court_name],
    ["Court level", p.court.judge_position],
    ["New cases filed in the past year", c.inflow_1y.toLocaleString("en-IN")],
    ["Cases from the past 2 years still pending", c.backlog_2y.toLocaleString("en-IN")],
    ["Queue ratio (pending ÷ yearly filings)", c.queue_ratio.toFixed(2)],
    ["Cases filed 1–2 years earlier now decided", c.clearance_1y === null ? "unknown" : percent(c.clearance_1y)],
  ];
  return (
    <table className="facts">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}><td>{k}</td><td>{v}</td></tr>
        ))}
      </tbody>
    </table>
  );
}
