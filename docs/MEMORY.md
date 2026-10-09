# Project Memory

## Current status (2026-10-09)
- **Week 1 done; Week 2 started.**
- 10,059,428 Maharashtra cases (2010–2018) are in `data/processed/cases_maharashtra.parquet`.
- Censoring cutoff 2020-09-10; 27.6% of cases are censored.
- `notebooks/01_explore.ipynb` audits every column.
- `case_category` and `is_criminal` were added (D-010). KM medians run from 12 days (bail) to
  1,664 days (RCC).
- Findings are in docs/DATA.md.

## Next step
Week 2 EDA in `notebooks/02_eda.ipynb`:
- duration distributions (Kaplan-Meier, not decided-only)
- pending share by filing year
- slowest districts and courts
- civil vs criminal and by `case_category`
- trends over 2010–2018
Save 5–6 charts to `reports/figures`. Drop `bad_dates` rows first.

## Open questions
- COVID (April 2020 on) is a structural break in decision rates. Options: model it, or end the
  observation window at 2020-03-15 and censor there. Decide in Week 3.
- ~~Cases with a disposition but no date~~: resolved. Only 1,717 cases (0.02%) are real ones,
  and they stay censored.
- Transferred and Lok Adalat referrals (~11% of decisions) count as events for now (D-005).
  Revisit as a competing risk in Week 3.
- `acts_sections` has not been downloaded yet. It comes after the cases in the zip and is large.
  Needs a disk-space check first.

## Archive
Unrelated "Agent Action Firewall" planning docs moved to `_archive/agent-action-firewall/`.
