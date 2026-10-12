import { Tile } from "../components/StatTiles";

interface InsightProps {
  title: string;
  text: string;
  figure: string;
  alt: string;
}

function Insight({ title, text, figure, alt }: InsightProps) {
  return (
    <section className="insight">
      <h2>{title}</h2>
      <p>{text}</p>
      <figure>
        <img src={`/figures/${figure}`} alt={alt} loading="lazy" />
      </figure>
    </section>
  );
}

// Findings from notebooks 03–05 (observation ends 2018-12-31, D-016). Numbers in docs/DATA.md.
const INSIGHTS: InsightProps[] = [
  {
    title: "Case type sets the clock",
    text: "Bail applications are typically decided in 12 days; regular warrant cases take a median of 3.8 years. No other factor comes close.",
    figure: "07_km_by_category.png",
    alt: "Kaplan-Meier curves of time to decision for 18 case categories",
  },
  {
    title: "Districts differ, even for the same case type",
    text: "After adjusting for case mix, cases in Gadchiroli are decided 1.8× as fast as in the average district, and cases in Thane 0.63× as fast.",
    figure: "08_district_adjusted.png",
    alt: "Adjusted district hazard ratios from a stratified Cox model",
  },
  {
    title: "Crowded courts are slower",
    text: "A court whose pending cases are a quarter of its yearly intake decides cases about 1.6× faster than average; one with 1.5 years of work waiting, about 0.9×.",
    figure: "15_shap_congestion.png",
    alt: "SHAP dependence of the decision rate on court congestion features",
  },
  {
    title: "What the model relies on",
    text: "Case type accounts for 44% of the model's explanation, court congestion for about 30%, and district for 13%.",
    figure: "14_shap_importance.png",
    alt: "Mean absolute SHAP value per feature",
  },
  {
    title: "Some fast districts are fast because their courts are less loaded",
    text: "Most district effects survive once congestion is accounted for. Nagpur is the exception: fifth fastest after adjusting for case type, but below average once its light court load is also taken into account.",
    figure: "17_shap_district.png",
    alt: "District effect on the decision rate after case type and congestion",
  },
  {
    title: "How good are the predictions?",
    text: "On 2016–2018 filings the boosted Cox model puts a pair of cases in the right order 70% of the time (C-index 0.699, against 0.651 for case type alone). Recent filings are decided slightly faster than it predicts.",
    figure: "12_calibration_by_year.png",
    alt: "Predicted vs observed share of cases decided, by test filing year",
  },
];

export function InsightsPage() {
  return (
    <>
      <p className="lede">
        What 10 million Maharashtra court cases filed 2010–2018 say about how long justice takes. Pending
        cases are kept as right-censored observations, not dropped, so slow cases are not hidden.
      </p>
      <div className="tiles">
        <Tile label="Cases analysed" value="10.0M" sub="Maharashtra, filed 2010–2018" />
        <Tile label="Median time to decision" value="1.5 years" sub="536 days, all cases" />
        <Tile label="Still pending at cutoff" value="30%" sub="end of 2018" />
        <Tile label="Courts covered" value="632" sub="in 40 districts and court systems" />
      </div>
      {INSIGHTS.map((i) => (
        <Insight key={i.figure} {...i} />
      ))}
    </>
  );
}
