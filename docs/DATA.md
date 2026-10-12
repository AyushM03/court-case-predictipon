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

### Week 2 EDA re-run under D-016 (`notebooks/02_eda.ipynb`, 2026-10-11)
Figures 01–06 now end observation at 2018-12-31. These numbers replace the Week 2 ones above.
- KM median **536 days** (decided-only 233); 57% / 33% / 19% still pending after 1 / 3 / 5 years.
- Category medians: bail 12 days to RCC warrant cases 3.8 years; execution 3.6 years, civil suits
  3.2 years. Civil 780 days vs criminal 445 days.
- Districts: Gadchiroli 0.3 years to Thane 2.3 years (MACT Mumbai 3.5 years); correlation with
  criminal share −0.48.
- Share decided within one year, 2010 → 2017 filings: criminal 37% → 49%, civil 27% → 39%.
  2018 filings are left out (no full year of follow-up).
- The tail is live: past 8 years, 8.1k of 72k cases at risk are decided; 8% still pending at
  8 years. The old "plateau after 9 years" is outside the observable window.

### Week 3 survival analysis (`notebooks/03_survival.ipynb`, 2026-10-11)
Observation ends 2018-12-31 (D-016, which replaced the 2020-03-15 cutoff of D-011; all numbers
below are from the re-run). Figures 07–10 are in `reports/figures/`.
- **The data freezes in mid-February 2019 (D-016).** Last hearings of 2.4M pending cases stop in
  the week of 11 February 2019. Recorded decisions run at about 110k a month through 2018, then
  88k (Jan 2019), 29k (Feb) and about 10k a month after. Censoring at 2018-12-31 moves 237k
  decisions (3.3%) to censored and the KM median from 583 to **536 days**.
- **Long-pending cases are live (D-012).** Of the 111k cases pending 9+ years, only 1.6% had no
  hearing in the two years before the cutoff. They stay censored.
- **Case type sets the clock.** KM medians run from 12 days (bail) to 3.8 years (regular warrant
  cases). The 18-category log-rank chi-square (3.3M) is 14× the district one (229k).
- **Log-rank p-values carry no information at this size.** Bhandara and Dhule have the same
  median (514 days) and still differ at p < 0.0001. Effect sizes are what count.
- **Adjusted district effects (stratified Cox):** from 0.63× the average district (Thane) to
  1.81× (Gadchiroli). Pune (0.79×), Nashik and Kolhapur are also slow. Sindhudurg, Ratnagiri and
  Nandurbar are fast.
- **Courts got slightly faster, not slower.** Each later filing year is decided about 2% faster
  (HR 1.023). With the 2020 cutoff this showed as a 3% slowdown per year, because recent
  filings carried most of the decisions missing after the freeze.
- **Case mix changes the middle of the ranking, not the ends.** The rank correlation between raw
  and adjusted rankings is 0.89. Jalna, Latur and Osmanabad move up 8–9 places once their slow
  case mix is accounted for, and Raigad drops 11.
- **Proportional hazards does not hold for districts.** The Schoenfeld test flags 12 of 40
  covariates. District effects in year 1 and after year 1 correlate only 0.47 (geographic
  districts). Wardha, Washim, Bhandara and Gondia are slow early but fast later, and Nagpur is
  the reverse. A single hazard ratio per district is an average over case age.
- **Concordance is 0.57** with district and year only, since category goes into the strata. This
  is not a prediction model yet.

### Week 4 congestion features (`features.py`, 2026-10-11)
Model table: 8,295,874 cases filed 2012-01-01..2018-12-31, censored at 2018-12-31 (D-016).
Built in about 1 min. The features only use decisions before each filing date, so the cutoff
change does not affect them.
- **Establishment-level counts are large.** Median `inflow_1y` is 3,110 and median `backlog_2y`
  3,436, because `court_no` is a court complex (median 7.6k cases over 2012–2018), not a courtroom.
- **`queue_ratio`** (median 1.17) and **`clearance_1y`** (median 0.49) both track duration
  monotonically. With the earlier 2020 cutoff, the median observed duration by `queue_ratio` quintile runs 104 → 449 → 519 →
  617 → 801 days; by `clearance_1y` quintile 788 → 164 days. These are raw (not KM, not adjusted
  for case type), and part of the effect is case mix: fast bail-heavy courts have short queues.
- 0.2% of cases have no `clearance_1y` (no filings in the court 1–2 years earlier).

### Week 4 model comparison (`notebooks/04_models.ipynb`, 2026-10-11)
Train on 2012–2015 filings (4.37M, 21% still pending), test on 2016–2018 filings (3.93M, 49%
pending), observation ends 2018-12-31 (D-015, D-016). Scored on a fixed 50k test sample up to
2 years; metrics in `reports/model_metrics.csv`, figures 11–13.

| model | Uno's C | integrated Brier | Brier 1y | Brier 2y | fit |
|---|---|---|---|---|---|
| KM by category (baseline) | 0.651 | 0.200 | 0.209 | 0.207 | 1 s |
| Cox, stratified by category (200k) | 0.692 | **0.188** | 0.195 | 0.199 | 33 s |
| XGBoost AFT, log-normal σ = 1.8 (1.5M) | 0.696 | 0.197 | 0.206 | 0.208 | 6 min |
| **XGBoost Cox + Breslow (1.5M)** | **0.699** | **0.188** | 0.195 | 0.197 | 5 min |

- **Features beyond case type add about 0.05 C-index** and cut the Brier score by 6%. Boosting
  adds little over a linear stratified Cox (0.699 vs 0.692 C, equal Brier).
- **AFT ranks well but is poorly calibrated.** Its single log-normal shape cannot fit the mix of
  same-day closures and multi-year cases; the tuned σ (1.8) is wide. Not worth pursuing.
- **What the boosted model uses (share of split gain):** case category 42%, congestion features
  38% (queue ratio 16%, clearance 8%, inflow 7%, backlog 7%), district 12%, judge position 8%.
- **Cox congestion effects (per SD, other features fixed):** more backlog for the same inflow
  means slower decisions (backlog HR 0.48, inflow 1.93: the two only make sense together), and
  courts that cleared more of their older cohort decide faster (clearance HR 1.08).
- **Calibration drifts with time.** 2016 filings are well calibrated. 2017 and 2018 filings are
  decided faster in their first year than predicted (about 6 points more decided at 6 months for
  2018), matching the ~2% per year speed-up in Week 3. Training only on older filings misses it.
- **Before D-016** (cutoff 2020-03-15) the same comparison gave the same ranking (C 0.650 /
  0.691 / 0.698 / 0.699) but observed curves flattened at the February 2019 data freeze.

### Week 4 SHAP explanations (`notebooks/05_shap.ipynb`, 2026-10-11)
Exact TreeSHAP from XGBoost (`pred_contribs`, native categoricals) for the XGBoost Cox model on
20k test cases (2016–2018 filings); 84 s. Values are log-hazard contributions, shown as
decision-rate multipliers (above 1× = decided sooner). Figures 14–18.
- **Share of total |SHAP|:** case category 44%, district 13%, queue ratio 12%, judge position 10%,
  backlog 6%, clearance 6%, inflow 6%, criminal flag 3%. Congestion together is about 30%.
- **Case category:** bail 8.4× the average case's rate, criminal misc 2.1×, family 1.7×; regular
  warrant cases 0.52×, execution 0.51×, arbitration/co-operative 0.42×.
- **Queue ratio has a clear dose-response:** about 1.6× at a ratio of 0.3, 1× near 1.1, 0.9× from
  1.5 up. Clearance rate rises gently from 0.95× to 1.15×. Inflow and backlog on their own add
  little once the ratio is in.
- **District effects mostly survive congestion** (rank correlation 0.81 with the Week 3 Cox
  ranking): Thane 0.73×, Raigad 0.80×, Pune 0.87× slowest; Gadchiroli 1.47×, Sindhudurg 1.45×,
  Wardha 1.38× fastest. **Nagpur** drops from 5th fastest (Week 3) to 27th of 32: its speed is
  explained by lightly loaded courts.
- **Worked example:** a 2016 Pune civil suit (queue ratio 1.58) gets 0.32× the average rate and a
  predicted median beyond 2 years; case type (0.63×), district (0.75×) and queue ratio (0.78×)
  drive it.
- SHAP explains the model, not causes: congestion and district are correlated and share credit.
