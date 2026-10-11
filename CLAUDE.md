# CLAUDE.md

Guide for Claude Code working in this repo. Keep the **Work log** at the bottom up to date.

## Project
"How Slow Is Justice?": predicts **case duration** in Indian district courts with survival analysis
on the Development Data Lab (DDL) e-Courts dataset (2010–2018). Scope: **Maharashtra** only.
Pending cases are **right-censored** and are never dropped (see `docs/DECISIONS.md` D-002).
The project predicts how fast the system is, not who wins, and does not score judges (D-006).

## Docs (read these first)
- `docs/MEMORY.md`: current status and the next step
- `docs/TASKS.md`: 6-week plan with checkboxes
- `docs/DATA.md`: data source, schema and findings log
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (append-only), `docs/PRD.md`

## Commands (Windows, run from repo root, use the venv python)
```bash
.venv/Scripts/python -m court_delay.fetch download cases     # stream zip -> data/raw/cases/cases.tar.gz
.venv/Scripts/python -m court_delay.fetch extract 2010       # optional: loose CSV (ingest doesn't need it)
.venv/Scripts/python -m court_delay.ingest --state Maharashtra --years 2010 --skip-acts
.venv/Scripts/python -m court_delay.categories               # add case_category to existing parquet
.venv/Scripts/python -m court_delay.features                 # congestion features -> model_maharashtra.parquet
.venv/Scripts/python -m pytest -q
```

## Data layout and gotchas
- **Source:** DDL Dropbox (`DDL_URL` in `src/court_delay/fetch.py`). It only downloads as one
  ~5.1 GB zip with no byte-range support, so `fetch download` streams it and saves only the
  wanted members. Inside the zip:
  - `csv/` and `dta/` hold the same data (CSV and Stata versions), and their members are
    interleaved in the stream. We keep only `csv/`.
  - `csv/keys/keys.tar.gz` is about 66 MB.
  - `csv/cases/cases.tar.gz` (~1.4 GB) holds **all years**.
  - `acts_sections` comes later in the zip and is very large.
  - Every member seen is logged to `data/raw/manifest.txt`.
- **Zip format:** Dropbox writes stored (uncompressed) members with a data descriptor and size 0,
  which `stream-unzip` rejects. `src/court_delay/ziptail.py` is our own streaming reader that
  finds each member's end by checking the CRC and size (tested in `tests/test_ziptail.py`).
- **Keys:** `data/raw/keys/*.csv` were converted from the Stata (`dta`) keys with
  `pandas.read_stata` (the CSV keys tarball was overwritten during the first fetch). Maharashtra
  = `state_code` 1 in every year. Key columns match `config.py`.
  `judge_case_merge_key.csv` (520 MB) is unused for now and can be deleted if disk is tight.
- **Disk:** A: has about 3.5 GB free.
  - Ingest streams `cases_<year>.csv` straight out of `cases.tar.gz` (D-008), so nothing needs
    extracting. A loose `cases_<year>.csv` in `data/raw/cases/` is used instead if present.
  - Keep `cases.tar.gz`: getting it again means another 5 GB download.
- **Censoring cutoff:** the 99.9th percentile of decision and last-hearing dates
  (`CUTOFF_QUANTILE`, D-007), because the raw max comes from typo dates (2022, 2101).
  Over all years it is 2020-09-10. Decisions collapse from April 2020 (COVID lockdown), which
  is a structural break to handle in modelling.
- **District key is cumulative, not per-year:** join on (state_code, dist_code) only (D-009).
  Joining on year left 9.2M rows without a district name.
- `data/` is gitignored. License CC BY-NC-SA 4.0, non-commercial.
- Column names live in `src/court_delay/config.py`. Fix any mismatch there, not in `ingest.py`.

## Work log
- **2026-10-07:** project scaffold, docs, and the ingest pipeline (state filter, key joins, duration and
  censoring) with tests on synthetic data. Commit `4e0ffdc`.
- **2026-10-08:**
  - Found the DDL Dropbox link.
  - Wrote `fetch.py` (download + extract) and `ziptail.py` (streaming zip reader) with tests.
    Added `httpx` to `requirements.txt`.
  - Downloaded the keys and converted them to CSV.
  - Downloaded `cases.tar.gz` (all years, 1.4 GB).
  - Ingest now streams from the tarball.
  - Ran 2010: 866,279 Maharashtra cases, 7.3% censored, decided median 619 days.
  - Cutoff changed from the max date (2022-02-20, from typos) to the 99.9th percentile
    (2019-08-21). Tests updated: 8 pass.
  - Findings are in `docs/DATA.md`.
  - Ingested all years 2010–2018: **10,059,428 cases**, cutoff 2020-09-10, 27.6% censored.
    Pending share by filing year runs from 7% (2010) to 55% (2018).
  - Fixed the district join (D-009). 9 tests pass.
- **2026-10-09:**
  - Wrote `notebooks/01_explore.ipynb`, a column audit of all 10M rows. Week 1 is done.
  - The court and purpose keys join 100% on (year, code).
  - The gender flags use the sentinels −9998 and −9999.
  - Only 1,717 cases have a real disposition with no date.
  - Transfer and Lok Adalat referrals are about 11% of decisions; decide how to treat them in
    Week 3.
  - 52k `bad_dates` rows are all negative; drop them.
  - 6.6% of cases close on the filing day.
  - The 1,160 type labels need mapping to categories.
  - Run notebooks with `nbclient`, because `jupyter nbconvert` crashes on a broken global
    `jupyter_contrib_nbextensions`.
  - Added `categories.py` (D-010):
    - It maps 1,160 type labels to 18 categories plus `is_criminal`, using regex rules and
      overriding them by `judge_position` for specialised courts. 0.2% of cases stay "other".
    - Ingest calls it, and `python -m court_delay.categories` adds the columns to the existing
      parquet in batches.
    - Kaplan-Meier medians run from 12 days (bail) to 1,664 days (RCC warrant cases).
      70% of cases are criminal.
    - 38 tests pass.
  - Committed `1ac5c03`.
  - Wrote `notebooks/02_eda.ipynb` with 6 charts in `reports/figures/` (reference dataviz
    palette: blue = criminal, orange = civil).
  - KM median 583 days vs decided-only 246. Civil 905 days, criminal 473.
  - Eight "districts" are Mumbai or statewide court systems (D-009 key).
  - The day-182 jump is the divorce cooling-off period.
  - KM flattens past 9 years: 112k cases at risk, 829 decided (stale records?).
- **2026-10-11:**
  - Parked `acts_sections` (A: has 3.2 GB free) and did Week 3.
  - Added `survival.py`:
    - `censor_at` ends observation at `ADMIN_CENSOR_DATE` 2020-03-15 (D-011).
    - `aggregate` collapses cases to (duration, event, n) for fast weighted KM.
  - 42 tests pass.
  - Only 0.03% of decisions fall in Mar–Sep 2020. The 111k cases pending 9+ years are still being
    heard, so they stay censored (D-012).
  - Wrote `notebooks/03_survival.ipynb` with figures 07–10:
    - The stratified Cox model (D-013) gives district hazard ratios from 0.64× (Thane) to 1.8×
      (Gadchiroli). Raw vs adjusted rank correlation is 0.90.
    - PH does not hold for districts: year 1 vs later r = 0.47.
  - Added a README section explaining censoring.
  - The notebook takes about 17 min. Build notebooks with `nbformat` from a script and run them
    with `nbclient`. When a builder script puts cell code in a Python string, a `\n` inside an f-string
    in that code must be written double-escaped (backslash-backslash-n). Otherwise the cell gets a
    literal line break and a SyntaxError.
  - Week 4 started: `features.py` adds court congestion features per establishment
    (`inflow_1y`, `backlog_2y`, `queue_ratio`, `clearance_1y`; D-014). It uses a numba Fenwick
    tree (added `numba` to requirements) and is checked against brute force. 45 tests pass.
  - `python -m court_delay.features` writes `data/processed/model_maharashtra.parquet`
    (8.3M cases filed 2012–2018) in about 1 min.
  - `court_no` is a court establishment (633 total), not a courtroom.
  - **Next:** time-based split, KM baseline, Cox, GBSA (see docs/MEMORY.md).
