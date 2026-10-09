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
