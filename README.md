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
