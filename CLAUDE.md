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
  - **Next:** `notebooks/01_explore.ipynb`, then Week 2 EDA.
