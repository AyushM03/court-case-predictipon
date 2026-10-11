# How Slow Is Justice? Predicting Case Duration in India's Lower Courts

A data science project that models **how long cases take** in India's district courts, using
survival analysis on the Development Data Lab (DDL) e-Courts dataset (81M cases, 2010–2018).
Scope: **Maharashtra** (one state keeps the data laptop-sized).

> The question is *how slow the system is*, not whether any individual litigant or judge is
> "good" or "bad". The model predicts duration from structural features (court, district, case
> type, act, court congestion). It does not predict who wins.

## Why this project is different
Many cases were **still pending** when the data was collected. Dropping them would bias every
estimate toward fast cases, because only the cases that already finished would remain. These
cases are **right-censored**: we know they lasted *at least* N days. Survival analysis
(Kaplan-Meier, Cox PH, gradient-boosted survival models) handles them correctly.

## Censoring, in plain English
Suppose a case was filed in March 2016 and was still open when the data was collected in 2020.
We don't know how long it will take, but we do know it took **at least 4 years**. That
"at least" is called **right-censoring**.

There are two easy mistakes:
- **Drop the open cases.** Only finished cases are left, and those are the faster ones. In this
  data the median for decided cases only is 246 days. The true median is about 580 days.
- **Treat "still open" as "finished today".** This cuts every slow case short and again makes
  courts look faster than they are.

Survival analysis does neither. **Kaplan-Meier** asks a question for each day: of the cases
still open that morning, what share got decided that day? Multiplying those daily shares together
gives the share of cases still pending after *t* days. A censored case counts for every day it was
known to be open, then leaves the calculation without being counted as decided. The **Cox model**
uses the same idea to compare groups, for example "cases in district A are decided 1.3× as fast
as in the average district, for the same case type".

Two practical choices: observation ends on 2020-03-15, before the COVID court shutdown
([D-011](docs/DECISIONS.md)). Cases pending for 9+ years are kept, because most still have
regular hearings ([D-012](docs/DECISIONS.md)).

## Stack
Python · pandas · pyarrow · lifelines · scikit-survival / XGBoost · SHAP · FastAPI · Streamlit or Next.js (demo)

## Project layout
```
data/raw/         DDL downloads (not committed)
data/interim/     state-filtered parquet per year
data/processed/   analysis-ready survival table
notebooks/        01_explore, 02_eda, 03_survival, 04_models
src/court_delay/  reusable pipeline code
tests/            pytest
docs/             PRD, architecture, decisions, tasks, data dictionary
```

## Quickstart
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m court_delay.fetch download keys cases   # streams the ~5 GB DDL zip, keeps what we need
python -m court_delay.ingest --state Maharashtra --years 2010-2018 --skip-acts
```

## Data & license
Data: Development Data Lab, *Judicial Data* (devdatalab.org/judicial-data), CC BY-NC-SA 4.0.
This project is non-commercial and inherits that license for derived data.

## Status
See `docs/MEMORY.md`.
