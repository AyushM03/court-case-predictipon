import type { Contribution } from "../api";

const MIN_EFFECT = 0.01;            // hide factors that change the rate by less than ~1%

/** SHAP contributions as diverging bars around 1× (no effect). Bar length is the log of the
 *  multiplier, so ×2 and ×0.5 are equally long. */
export function Drivers({ items, max = 7 }: { items: Contribution[]; max?: number }) {
  const shown = items.filter((c) => Math.abs(Math.log(c.multiplier)) >= MIN_EFFECT).slice(0, max);
  const scale = Math.max(Math.log(2), ...shown.map((c) => Math.abs(Math.log(c.multiplier))));
  return (
    <>
      <div className="why">
        {shown.map((c) => {
          const v = Math.log(c.multiplier);
          const width = `${(Math.abs(v) / scale) * 50}%`;
          return (
            <div key={c.feature} style={{ display: "contents" }}>
              <div className="name">
                {c.label}
                <small>{c.value}</small>
              </div>
              <div className="bar" aria-hidden="true">
                <span className={v >= 0 ? "up" : "down"} style={{ width }} />
              </div>
              <div className="mult" aria-label={`${v >= 0 ? "decided sooner" : "decided later"}, times ${c.multiplier.toFixed(2)}`}>
                ×{c.multiplier.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="why-legend">
        <span><span className="swatch" style={{ background: "var(--orange)", marginRight: 5 }} />decided later</span>
        <span>decided sooner<span className="swatch" style={{ background: "var(--blue)", marginLeft: 5 }} /></span>
      </div>
    </>
  );
}
