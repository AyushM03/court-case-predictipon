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

## D-015: Model comparison design (2026-10-11)
- **Split by filing year:** train on 2012–2015 filings, test on 2016–2018. Filing year is not a
  feature, because trees cannot extrapolate it and a linear trend would extrapolate blindly.
  Time-varying load enters through the congestion features (D-014).
- **One output for every model:** survival probabilities on a 15-day grid up to 2 years (D-016)
  (`models.GRID`), so all models are scored the same way. Ranking uses −RMST up to 2 years
  rather than each model's own risk score.
- **Metrics:** Uno's IPCW C-index and integrated Brier score over 30–730 days, plus Brier at
  1 and 2 years. The IPCW censoring distribution is estimated on the test set, because test
  filings are far more censored than training ones (49% vs 21% still pending, D-016 cutoff). Uno's C is
  quadratic in sksurv, so evaluation uses a fixed 50k test sample.
- **Samples for RAM (7.9 GB machine):** the Cox model is fitted on 200k cases, XGBoost on 1.5M
  with 200k for early stopping, and the KM baseline on the full training set.

## D-016: Observation ends 2018-12-31, the data freeze (replaces D-011) (2026-10-11)
Most case records were last updated in mid-February 2019. The last hearing dates of 2.4M pending
cases stop in the week of 11 February 2019, and recorded decisions fall from about 110k a month
through December 2018 to 88k in January, 29k in February and around 10k a month after that.
Only a minority of records were refreshed in 2020. A case decided after the freeze therefore
still looks pending, and censoring at 2020-03-15 (D-011) counted 13+ months of missing records as
cases still waiting, which inflated durations, most of all for recent filings. All survival
models now censor at `ADMIN_CENSOR_DATE` = 2018-12-31, the last month with complete decision
records. The congestion features (D-014) are unaffected because they only use decisions before
each filing date, and all filings are 2018 or earlier. The evaluation horizon in D-015 is 2 years,
because 2018 test filings have at most one year of follow-up.

## D-017: The API serves an XGBoost Cox model refit on all 2012–2018 filings (2026-10-11)
- **Two models.** The evaluation model (`data/models/eval`, trained on 2012–2015 filings) backs the
  reported metrics and SHAP. Once the model was chosen, `python -m court_delay.train` refits it the
  same way (1.5M sample, 200k early stopping, same parameters) on all 2012–2018 filings into
  `data/models/deploy`. This uses the most recent court conditions and reduces the calibration
  drift seen for 2017–2018 filings. The deployment model has no held-out test score of its own.
- **Daily baseline.** `XGBCox` keeps the Breslow baseline for every day up to the longest training
  duration (about 7 years), and the API shows curves to 5 years.
- **Prediction setting.** A request is a case type in a court. Its congestion features are the
  court's values for a case filed on 2019-01-01 (`features.court_snapshot`, the same code as
  training), and district and judge position come from the court. Courts with no filings in 2018
  are left out (632 remain).
- **Category encoding.** XGBoost reads pandas categoricals by code, so the training category lists
  are stored in `meta.json` and every request is encoded with them (`models.prepare(categories=)`).
- **Comparison.** Each prediction ranks the court's median among all courts that hear that case
  type (at least 20 filings 2016–2018). This compares court establishments, not judges (D-006).

## D-018: Deploy as one Docker container (2026-10-11)
FastAPI serves the API, the built React app (`frontend/dist`) and `reports/figures` from one
process, so there is no cross-origin setup and one URL to host. The image is multi-stage (Node
builds the front end; `python:3.12-slim` runs it) and installs only `requirements-api.txt`, with
`xgboost-cpu` instead of `xgboost` to avoid the CUDA libraries. The API's import chain no longer
pulls in numba, lifelines or scikit-survival (`DEPLOY` and `MODEL_FILE` moved to `config.py`). The
model files are baked into the image (22 MB), which is simpler than fetching them at start-up.
It listens on `$PORT`, runs as a non-root user and has a health check, so it runs on any
container host. Predictions from the container match the local ones exactly.

## D-019: Host on Vercel with Services; API under /api, predictions without pandas (2026-10-11)
The user chose Vercel. Vercel does not run the D-018 container as-is, so the project uses
Vercel Services (beta): a static `web` service (`frontend/`, Vite) and a Python `api` service
(`backend/`, FastAPI), routed by `vercel.json` (`/api/*` to the API, everything else to the app,
with an index.html fallback for client routes).
- **The API lives under `/api/*` everywhere** (local, Docker, Vercel): Vercel passes the full path
  to the service, so one convention avoids rewrites. Docs are at `/api/docs`.
- **A service bundles only its own folder.** Checked with `vercel build`: files outside `backend/`
  are left out unless listed in `includeFiles`, whose paths are relative to the service root
  (`../src/court_delay/**/*.py`). The model is exported into `backend/model/` (tracked, so Git
  deployments have it) with `python -m court_delay.train --export backend/model`.
- **Bundle size.** With pandas the function bundle was 263 MB, above the 250 MB size at which
  Vercel switches to installing dependencies at runtime. `inference.py` now builds the feature
  matrix with numpy and calls XGBoost directly; it matches the pandas path exactly (0 difference
  in margin, survival and SHAP over all 12,008 court × case type combinations; tests in
  `tests/test_inference.py`). The booster is exported as UBJSON (16 MB instead of 22 MB). The
  bundle is now 223 MB: scipy (required by XGBoost) 112 MB, numpy 54 MB, XGBoost 23 MB, model 17 MB.
  Constants the API needs moved to the dependency-free `labels.py`; the court table is JSON.
- **Figures** are copied into `frontend/public/figures` before each build
  (`frontend/scripts/copy-figures.mjs`), so the static service serves them.
- **Caveats.** Services is a beta feature. `vercel dev` serves the app's index.html for
  `/figures/*` (its dev router rewrites before Vite's public folder); the production route table
  checks files first, so this affects local `vercel dev` only. Cold starts load the model
  (about 2 s); the Docker image (D-018) remains an alternative host.

## D-020: Host on Render with the Docker image (2026-10-12)
The Vercel deploy (D-019) built but failed at "Deploying outputs", and the user chose Render
instead. Render builds the D-018 `Dockerfile` from GitHub (`render.yaml` Blueprint, free plan,
health check `/api/health`). The image now copies the committed `backend/model/` (UBJSON) and sets
`COURT_DELAY_MODEL_DIR`, so it no longer needs the gitignored `data/models/deploy/`. Free instances
sleep after ~15 minutes idle, so the first request after a pause takes about a minute.
