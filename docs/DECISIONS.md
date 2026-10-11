# Decisions

Append new entries instead of editing old ones.

## D-001 — One state (Maharashtra)
81M rows do not fit comfortably on a laptop (and A: has ~6 GB free). Maharashtra has a large
caseload and a well-populated e-Courts presence. Pipeline is parameterised by state name so others can be added.

## D-002 — Treat pending cases as right-censored, never drop them
Dropping undecided cases biases durations downward. All duration modelling uses survival methods.

## D-003 — Parquet for interim/processed data
Columnar, typed, ~5–10× smaller than CSV and much faster to load. Raw CSVs can be deleted after ingest.

## D-004 — Time-based train/test split
Mimics real use (predict new filings from past ones) and avoids leakage through court-level features.

## D-005 — Disposal type treated as a single "decided" event (for now)
Any decision date counts as the event, including transfers and withdrawals. Competing-risks
analysis (e.g. transfer vs judgment) is a possible later extension.

## D-006 — Predict system speed, not outcomes
No outcome prediction, no judge-level scoring in the app.

## D-007: Censoring cutoff = 99.9th percentile of observed dates, not the max (2026-10-08)
The raw max is driven by typo dates. In 2010, a 2022 first hearing gave a cutoff of 2022-02-20.
The 99.9th percentile of `date_of_decision` and `date_last_list` gives 2019-08-21, which matches
when DDL collected the data. Set by `CUTOFF_QUANTILE` in `config.py`.

## D-008: Stream case years from `cases.tar.gz` instead of extracting (2026-10-08)
DDL ships all years in one 1.4 GB tarball (2.7 GB for 2018 once extracted), and A: has about
3.5 GB free. Ingest reads each year's CSV straight out of the tarball.

## D-009: Join districts on (state_code, dist_code), ignoring year (2026-10-08)
DDL's district key lists each district once, under the year it first appeared, so it is not a
per-year table. The type, disposition and state keys are per-year and stay joined on year.

## D-010: Rule-based `case_category` from type label + judge position (2026-10-09)
Maharashtra has 1,160 free-text type labels for a few dozen real case types. `categories.py`
maps them to 18 categories plus `is_criminal`. The rules are ordered regexes on the normalised
label. Specialised courts (family, labour/industrial, co-operative, MACT, juvenile) are
recognised from `judge_position` first, because their labels ("petition a", "appeal") are
ambiguous. Magistrate cases are split into summary (SCC / summons) and regular (RCC / warrant).
0.2% of cases stay "other". Rules are kept instead of a hand-made lookup table so that new years
and states map without editing a table.

## D-011: Survival models end observation on 2020-03-15 (2026-10-11)
Decision rates collapse from late March 2020 (COVID lockdown). Leaving those months in would
read the lockdown as courts getting slower. Models call `survival.censor_at(df)`, which censors
any case still open on `ADMIN_CENSOR_DATE` (or decided after it) at that date. The processed
parquet keeps the 2020-09-10 cutoff (D-007), so both views stay available. In practice few
decisions fall in the gap, so the KM median moves only from 583 to 579 days.

## D-012: Cases pending 9+ years stay censored, not dropped or flagged as stale (2026-10-11)
About 111k cases were pending 9+ years at the cutoff. Only ~4% of them had no hearing in the two
years before it, so they are mostly live cases that courts keep listing, not abandoned records.

## D-013: Stratified Cox for district comparisons, with deviation coding (2026-10-11)
Case categories have very different baseline hazards (bail in days, warrant cases in years), so
the Cox model is stratified by `case_category` instead of using category dummies. District uses
deviation (sum-to-zero) coding, so each hazard ratio is relative to the average district, not to
an arbitrary reference. The model is fitted on a 300k random sample: the full 10M rows only add
runtime.

## D-014: Court congestion as look-back counts per establishment, from 2012 filings (2026-10-11)
`court_no` is a court establishment (633 in Maharashtra), not a courtroom, so congestion is
measured per (dist_code, court_no). For a case filed on day t the features count only what was
known on t: `inflow_1y` (filings in the past year), `backlog_2y` (filings in the past two years
not yet decided), `queue_ratio` (backlog / inflow) and `clearance_1y` (share of the cohort filed
1–2 years earlier that was decided by t). A full "all pending cases" count is not possible
because the data starts in 2010 with no older backlog, so fixed windows are used instead, and the
model table starts at 2012-01-01 so every window is complete. `features.py` builds
`data/processed/model_maharashtra.parquet` (8.3M cases) with a numba Fenwick-tree pass per court,
checked against a brute-force count in `tests/test_features.py`.
