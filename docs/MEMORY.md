# Project Memory

## Current status (2026-10-09)
- **Week 1 done; Week 2 mostly done** (`notebooks/02_eda.ipynb`, 6 charts in
  `reports/figures/`). Only the slowest acts and sections are left.
- 10,059,428 Maharashtra cases (2010–2018) are in `data/processed/cases_maharashtra.parquet`.
- Censoring cutoff 2020-09-10; 27.6% of cases are censored.
- `notebooks/01_explore.ipynb` audits every column.
- `case_category` and `is_criminal` were added (D-010). KM medians run from 12 days (bail) to
  1,664 days (RCC).
- KM median 583 days (decided-only 246). Civil 905 vs criminal 473 days.
- Findings are in docs/DATA.md.

## Next step
Either:
- finish Week 2 by downloading `acts_sections` (check disk first, ~3 GB free) and charting the
  slowest acts and sections, or
- start Week 3: Kaplan-Meier with log-rank tests, then a Cox PH model adjusted for case mix
  (district rankings are confounded, with corr −0.5 against criminal share).

## Open questions
- COVID (April 2020 on) is a structural break in decision rates. Options: model it, or end the
  observation window at 2020-03-15 and censor there. Decide in Week 3.
- ~~Cases with a disposition but no date~~: resolved. Only 1,717 cases (0.02%) are real ones,
  and they stay censored.
- Transferred and Lok Adalat referrals (~11% of decisions) count as events for now (D-005).
  Revisit as a competing risk in Week 3.
- `acts_sections` has not been downloaded yet. It comes after the cases in the zip and is large.
  Needs a disk-space check first.

- 112k cases are still pending after 9+ years, and almost none of them get decided (829). These
  may be stale records: censor them, keep them, or flag them? Decide in Week 3.
- Eight `district_name` values are court systems, not districts. Handle them as their own
  group in models.

## Archive
Unrelated "Agent Action Firewall" planning docs moved to `_archive/agent-action-firewall/`.
