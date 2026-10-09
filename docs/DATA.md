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
`decision_date`, `event` (1 = decided, 0 = pending/censored), `duration_days`, `bad_dates` (flag),
`case_category` (18 groups + `other`, D-010), `is_criminal` (1/0, NA for `other`).

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

### Column audit, all years (`notebooks/01_explore.ipynb`, 2026-10-09)
- **Nulls:**
  - Decision date: 27.5% (the pending cases).
  - `purpose_name`: 2.2%.
  - Hearing dates: 1.3–1.6%.
  - Labels: 0%.
- **Court key:** joins 100% on (year, dist_code, court_no). It is per year, unlike the district
  key. There are 633 courts, and 11 change name over the years.
- **Purpose key:** joins 100% on (year, code). Codes are year-specific (5,550 distinct), so they
  must be normalised before use as a feature.
- **Gender flags:** these use the sentinels −9998 (unclear) and −9999 (missing name), not NaN.
  - Petitioner gender is unclear for 48% of cases (often the State or a company).
  - Defendant-advocate gender is missing for 76%.
  - Treat all of them as categories.
- **Dispositions:** the "1,022 cases with a disposition but no decision date" figure counted
  `disposition var missing` as a disposition. Only **1,717 cases (0.02%) across all years** have a
  real disposition with no date, so leaving them censored is fine. 33,329 decided cases have
  `disposition var missing`, and they are still decided.
- **Transferred** (~236k) and **referred to Lok Adalat** (~546k) make up about 11% of decisions.
  They close the case in this court without resolving the dispute. Decide in Week 3 whether to
  treat them as an event, as censoring, or as a competing risk.
- **Durations:**
  - All 52,370 `bad_dates` rows have negative durations (minimum −5,526 days), and no other row
    is negative. Drop them before fitting.
  - 668,934 cases (6.6% of all, 9.2% of decided) close on the filing day. Floor these at 0.5 days
    for parametric and AFT models.
  - 50,007 rows have a first hearing before filing (typos).
- **Case types:** there are 1,160 messy labels, such as `ss cases`, `ss casess` and `s s`.
  The top 10 cover 70%, the top 50 cover 91% and the top 100 cover 96%. Map them to a
  `case_category` and a civil/criminal flag in Week 2.
- **`judge_position`:** 70 free-text values that mix the court type with the judge's
  designation.

### Case categories (`court_delay.categories`, 2026-10-09)
70.3% of cases are criminal. The Kaplan-Meier median uses the right-censored durations and
excludes `bad_dates` rows.

| category | cases | pending | KM median (days) |
|---|---:|---:|---:|
| bail_remand | 437k | 0.3% | 12 |
| criminal_misc | 1.24M | 12% | 97 |
| succession | 30k | 9% | 140 |
| civil_misc | 426k | 16% | 218 |
| family | 374k | 17% | 383 |
| summary_criminal (SCC) | 3.75M | 25% | 534 |
| juvenile | 51k | 22% | 559 |
| criminal_appeal_revision | 163k | 27% | 777 |
| labour | 160k | 31% | 1,007 |
| motor_accident | 267k | 31% | 1,141 |
| sessions_special | 192k | 42% | 1,189 |
| arbitration_cooperative | 137k | 46% | 1,234 |
| domestic_violence | 60k | 52% | 1,266 |
| land_acquisition | 120k | 29% | 1,285 |
| civil_suit | 964k | 41% | 1,379 |
| civil_appeal_revision | 180k | 37% | 1,407 |
| execution | 319k | 45% | 1,569 |
| regular_criminal (RCC) | 1.12M | 47% | 1,664 |
| other | 20k | 27% | 519 |

There is a 140× spread between the fastest category (bail) and the slowest (warrant cases).
Execution of decrees (darkhast) takes longer than the suits that produce those decrees.

### Week 2 EDA (`notebooks/02_eda.ipynb`, 2026-10-09)
These figures exclude `bad_dates` rows (10,007,058 cases left). Charts are in `reports/figures/`.
- **KM median: 583 days.** The decided-only median is 246 days. After 1, 3 and 5 years, 58%,
  37% and 26% of cases are still pending.
- **Civil vs criminal medians:** 905 vs 473 days.
- **Districts:** medians run from 107 days (Gadchiroli) to 1,018 days (Thane). The correlation
  with criminal share is −0.5, so the ranking reflects case mix and needs adjusting in a Cox model.
- **Court systems in the district key:** eight `district_name` values are Mumbai court systems
  or statewide tribunals, not geographic districts:
  - Mumbai: City Civil Court, CMM Courts, Small Causes Court, Motor Accident Claims Tribunal
  - Statewide: Maharashtra Family Courts, Industrial and Labour Courts, School Tribunals,
    State Co-operative Appellate Court
  - Mumbai MACT is the slowest of all at 1,554 days.
- **Trend, measured as the share decided within a year (KM), which is fair across cohorts:**
  - criminal: 37% (2010) → 47% (2018)
  - civil: 27% → 39% (2017) → 32% (2018)
- **Day-182 jump:** decisions jump from about 5.7k to about 10k per day, driven by family
  judgements. This matches the 6-month cooling-off period for mutual-consent divorce
  (HMA s.13B), so it is real, not an artifact.
- **Plateau after 9 years:** 112k cases are at risk past 9 years, but only 829 of them are
  decided, so the curve flattens at about 14% still pending. These are probably stale or
  abandoned records. Consider this before fitting parametric tails.
- **Slowest courts:** CIVIL COURT J.D. VASAI (64% still pending) and JMFC III Kalyan had decided
  fewer than half their cases by the cutoff. These are court establishments only; there is no
  judge-level scoring (D-006).
