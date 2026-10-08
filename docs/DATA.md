# Data Guide

## Source
Development Data Lab, Judicial Data: https://www.devdatalab.org/judicial-data
Files are in a Dropbox folder linked from that page (it has to be opened in a browser).
License: CC BY-NC-SA 4.0. Cite DDL in the README.

## What to download (Week 1)
Free disk on A: is only about 6 GB, so download **one year at a time**.

1. `keys` (lookup tables, small): put the CSVs in `data/raw/keys/`
2. `cases` for **2010**: put `cases_2010.csv` (or `.csv.gz`) in `data/raw/cases/`
3. Later: `acts_sections` (large, a few GB): put it in `data/raw/`, ingest, then delete the raw copy

If a download is a `.tar.gz` archive, extract it with `tar -xzf <file> -C data/raw/...`.
After ingest writes `data/interim/cases_maharashtra_2010.parquet`, you can delete the raw year CSV.

## Expected schema (from DDL documentation; verify on first load)
**cases_YYYY.csv**, one row per case:
| column | meaning |
|---|---|
| ddl_case_id | unique case id (join key to acts_sections) |
| year | filing year |
| state_code, dist_code, court_no | location codes (joined via keys) |
| cino | e-Courts case number |
| judge_position | designation of the presiding judge |
| female_defendant, female_petitioner, female_adv_def, female_adv_pet | inferred gender flags |
| type_name | case type code |
| purpose_name | purpose of the latest hearing code |
| disp_name | disposition code (blank if pending) |
| date_of_filing, date_of_decision | lifecycle dates |
| date_first_list, date_last_list, date_next_list | hearing dates |

**keys/**: `cases_state_key.csv`, `cases_district_key.csv`, `cases_court_key.csv`,
`type_name_key.csv`, `disp_name_key.csv`, `purpose_name_key.csv`, `act_key.csv`, `section_key.csv`.
Most keys include a `year` column because codes can differ by year, so join on (year, code).

**acts_sections.csv**: ddl_case_id, act, section, bailable_ipc, number_sections_ipc, criminal.

If the real names differ, edit `src/court_delay/config.py`. The ingest script prints the actual
columns when one it expects is missing.

## Processed table: `data/processed/cases_<state>.parquet`
Raw columns plus: `state_name`, `district_name`, `type_label`, `disp_label`, `filing_date`,
`decision_date`, `event` (1 = decided, 0 = pending/censored), `duration_days`, `bad_dates` (flag).

## Findings log
### Download layout (verified 2026-10-08)
- The Dropbox folder downloads only as one ~5.1 GB zip, with `csv/` and `dta/` copies of everything.
- `csv/keys/keys.tar.gz` has 9 key tables, including `judge_case_merge_key` (520 MB, unused so far).
- `csv/cases/cases.tar.gz` (1.4 GB) holds **all years** as plain CSVs: 0.86 GB (2010) up to 2.7 GB (2018).
  Ingest streams each year straight out of this archive, with nothing extracted.
- Get it with `python -m court_delay.fetch download cases`.

### Keys
- Maharashtra is `state_code` **1** in every year.
- Key column names match `config.py`.
- **The district key is not per-year.** Each district is listed once, under the year it first
  appeared (625 rows for 2010; a few for 2011, 2014 and 2017). Joining on year left 9.2M rows
  from 2011–18 without a district name, so it is now joined on (state_code, dist_code) only
  (D-009). Two codes have corrected spellings, and the latest one is used:
  Jaipur Metro → Jaipur Metro I, Hoshiarpurr → Hoshiarpur.
- The type, disposition and state keys do cover every year from 2010 to 2018.
- In `type_name_key`, the codes load as floats (1.0). The joins still match.

### cases_2010 (Maharashtra)
- 866,279 of 4,281,327 national rows (20%). 40 districts, 637 case-type labels.
  Every district, type and disposition code joins to a label.
- Null rates:
  - `date_of_filing`: 0%
  - `date_of_decision`: 7.1%
  - `date_first_list`: 0.9%
  - `date_last_list`: 2.9%
- **Typo dates:**
  - `date_first_list` goes up to 2022.
  - `date_next_list` goes up to 2101.
  - Real activity stops around early 2020: 2,794 decisions in 2019 and 173 in 2020.
  - So the censoring cutoff is the 99.9th percentile of decision and last-hearing dates
    (D-007), which gives **2019-08-21**.
- **Bad dates:** 19,476 rows (2.2%). All have the decision date before the filing date.
- 432 decisions fall after the cutoff and are treated as censored at the cutoff.
- 1,022 cases have no decision date but do have a disposition label. They are treated as
  pending for now. Look into them in Week 2.
- Decided cases: median 619 days, mean 834 days. Pending: about 3,330 days (censored at the cutoff).
  These are 2010-only numbers, computed with a 2010-only cutoff of 2019-08-21.

### All years 2010–2018 (Maharashtra)
- **10,059,428 cases**, about 20% of national rows every year (866k in 2010, 1.37M in 2018).
  All 40 districts are labelled.
- Bad dates: 52,370 (0.5%).
- **Cutoff 2020-09-10** (99.9th percentile).
  - Decisions run at about 8k/month in Jan–Feb 2020 and 3.3k in March.
  - They fall to about 10–24/month in April–May 2020 (**COVID lockdown**), then 100–570/month
    from June to September.
  - The handful of later dates are typos (2101, 2116).
  - COVID is a structural break to handle in modelling.
- Pending share rises steeply by filing year: 7.3% (2010), 11.4% (2012), 36% (2016),
  44% (2017), 55.5% (2018). Overall 27.6% are censored.
- The decided-only median is 246 days, which is heavily biased low. Use Kaplan-Meier.
