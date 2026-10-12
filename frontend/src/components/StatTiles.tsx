import type { Prediction } from "../api";
import { formatDuration, percent, rankPhrase } from "../format";

interface TileProps {
  label: string;
  value: string;
  sub?: string;
}

export function Tile({ label, value, sub }: TileProps) {
  return (
    <div className="tile">
      <div className="k">{label}</div>
      <div className="v">{value}</div>
      {sub && <div className="s">{sub}</div>}
    </div>
  );
}

export function StatTiles({ p }: { p: Prediction }) {
  const [q1, , q3] = p.quartile_days;
  const cmp = p.comparison;
  const rank = rankPhrase(cmp.share_of_courts_slower);
  return (
    <div className="tiles">
      <Tile
        label="Typical time to decision"
        value={formatDuration(p.median_days)}
        sub={q1 !== null ? `Half of cases between ${formatDuration(q1)} and ${formatDuration(q3)}` : undefined}
      />
      <Tile label="Decided within 1 year" value={percent(p.decided_by["1y"])} sub={`${percent(p.decided_by["2y"])} within 2 years`} />
      <Tile label="Decided within 3 years" value={percent(p.decided_by["3y"])} sub={`${percent(p.decided_by["5y"])} within 5 years`} />
      {cmp.courts_hearing_category > 1 ? (
        <Tile
          label="Compared with other courts"
          value={rank.head}
          sub={`${rank.tail} hearing this case type (${cmp.courts_hearing_category}); typical ${formatDuration(cmp.statewide_median_days)}`}
        />
      ) : (
        <Tile label="Compared with other courts" value="–" sub="Too few courts hear this case type" />
      )}
    </div>
  );
}
