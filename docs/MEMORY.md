# Project Memory

## Current status (2026-10-08)
- Week 1 nearly done. All years 2010–2018 are ingested: 10,059,428 Maharashtra cases in
  `data/processed/cases_maharashtra.parquet`.
- Censoring cutoff 2020-09-10; 27.6% of cases are censored.
- Findings are in docs/DATA.md.

## Next step
Build `notebooks/01_explore.ipynb`: column meanings, null rates and code→name checks.
Then move on to Week 2 EDA.

## Open questions
- COVID (April 2020 on) is a structural break in decision rates. Options: model it, or end the
  observation window at 2020-03-15 and censor there. Decide in Week 3.
- 1,022 cases (in 2010 alone) have a disposition but no decision date. Treat them as decided?
  (A decision date would be needed.)
- `acts_sections` has not been downloaded yet. It comes after the cases in the zip and is large.
  Needs a disk-space check first.

## Archive
Unrelated "Agent Action Firewall" planning docs moved to `_archive/agent-action-firewall/`.
