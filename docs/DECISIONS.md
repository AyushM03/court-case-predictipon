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
