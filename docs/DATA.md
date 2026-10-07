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
(Record what you learn about each column in Week 1 here: null rates, odd codes, surprises.)
