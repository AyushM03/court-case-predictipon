import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchMeta, fetchPrediction, type Meta, type Prediction } from "../api";
import { CourtPicker, type Selection } from "../components/CourtPicker";
import { DecisionCurve } from "../components/DecisionCurve";
import { Drivers } from "../components/Drivers";
import { StatTiles } from "../components/StatTiles";
import { Workload } from "../components/Workload";
import { formatDuration } from "../format";

const DEFAULT_DISTRICT = "Pune";

/** Selection from the URL (?court=25-6&case=civil_suit) if valid, else a sensible default. */
export function initialSelection(meta: Meta, courtId: string | null, category: string | null): Selection {
  for (const d of meta.districts) {
    const c = d.courts.find((x) => x.court_id === courtId);
    if (c) {
      const known = meta.case_categories.some((k) => k.id === category);
      return { district: d.district, courtId: c.court_id, category: known ? category! : c.categories[0] };
    }
  }
  const d = meta.districts.find((x) => x.district === DEFAULT_DISTRICT) ?? meta.districts[0];
  const c = d.courts.find((x) => x.categories.includes("civil_suit")) ?? d.courts[0];
  return { district: d.district, courtId: c.court_id, category: c.categories[0] };
}

export function PredictPage() {
  const [params, setParams] = useSearchParams();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sel, setSel] = useState<Selection | null>(null);
  const [pred, setPred] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    fetchMeta(ctl.signal)
      .then((m) => {
        setMeta(m);
        setSel(initialSelection(m, params.get("court"), params.get("case")));
      })
      .catch((e) => e.name !== "AbortError" && setError(`Could not load courts: ${e.message}`));
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!sel) return;
    setParams({ court: sel.courtId, case: sel.category }, { replace: true });
    const ctl = new AbortController();
    setLoading(true);
    setError(null);
    fetchPrediction(sel.courtId, sel.category, ctl.signal)
      .then(setPred)
      .catch((e) => e.name !== "AbortError" && setError(e.message))
      .finally(() => !ctl.signal.aborted && setLoading(false));
    return () => ctl.abort();
  }, [sel, setParams]);

  if (!meta || !sel) {
    return <p className={`status${error ? " error" : ""}`} role="status">{error ?? "Loading courts…"}</p>;
  }

  return (
    <>
      <CourtPicker meta={meta} value={sel} onChange={setSel} />
      <p className={`status${error ? " error" : ""}`} role="status">
        {error ??
          (loading
            ? "Predicting…"
            : pred && `${pred.case_category_label} cases filed at ${pred.court.court_name}, under the court's workload on ${pred.snapshot_date}.`)}
      </p>

      {pred && (
        <section className={`result${loading ? " loading" : ""}`}>
          {pred.warnings.map((w) => (
            <p key={w} className="warning">{w}</p>
          ))}
          <StatTiles p={pred} />

          <div className="card">
            <h2>Chance the case has been decided</h2>
            <p className="sub">
              By time since filing. Half of cases are decided by the median ({formatDuration(pred.median_days)});
              the dashed grey line is the median across the {pred.comparison.courts_hearing_category} courts that hear
              this case type.
            </p>
            <DecisionCurve
              curve={pred.curve}
              medianDays={pred.median_days}
              typicalDays={pred.comparison.statewide_median_days}
              horizonDays={meta.horizon_days}
            />
          </div>

          <div className="grid2">
            <div className="card">
              <h2>What drives this estimate</h2>
              <p className="sub">Each factor's effect on the decision rate, compared with an average case.</p>
              <Drivers items={pred.explanation} />
            </div>
            <div className="card">
              <h2>The court's workload</h2>
              <p className="sub">As of {pred.snapshot_date}, the latest the data allows.</p>
              <Workload p={pred} />
            </div>
          </div>
        </section>
      )}
    </>
  );
}
