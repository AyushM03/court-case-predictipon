# Project Memory

## Current status (2026-10-11)
- **Weeks 1–3 done.** Week 2's acts/sections chart is parked (needs the `acts_sections` download;
  A: has 3.2 GB free).
- 10,059,428 Maharashtra cases (2010–2018) are in `data/processed/cases_maharashtra.parquet`
  (10,007,058 after dropping `bad_dates`).
- `notebooks/03_survival.ipynb`: KM by category, log-rank tests, a stratified Cox model of
  district effects, and PH checks. Figures 07–10. It runs in about 17 min (mostly Cox fits).
- `src/court_delay/survival.py`: `censor_at` (COVID cutoff, D-011), `aggregate` (weighted KM),
  `is_court_system`.
- Adjusted district hazard ratios run from 0.64× (Thane) to 1.8× (Gadchiroli). District effects
  are not proportional over case age (year 1 vs later r = 0.47).
- Findings are in docs/DATA.md.

## Next step
Week 4, starting with the **court congestion feature**: pending cases in the same court
(`court_no` within district) on the filing date. Then a time-based split (train 2010–2015 filings,
test 2016–2018), the KM-median baseline, a full Cox model, and a gradient-boosted survival model,
compared on C-index and integrated Brier score.

## Open questions
- ~~COVID structural break~~: resolved, observation ends 2020-03-15 (D-011).
- ~~Cases with a disposition but no date~~: resolved. Only 1,717 cases (0.02%) are real ones,
  and they stay censored.
- Transferred and Lok Adalat referrals (~11% of decisions) count as events for now (D-005).
  Competing risks is still an option for a later extension.
- `acts_sections` has not been downloaded yet. It comes after the cases in the zip and is large.
  Needs a disk-space check first.

- ~~112k cases pending 9+ years~~: resolved, they are live (still heard) and stay censored (D-012).
- Eight `district_name` values are court systems, not districts. Handle them as their own
  group in models.

## Archive
Unrelated "Agent Action Firewall" planning docs moved to `_archive/agent-action-firewall/`.
