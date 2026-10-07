# Architecture

## Data flow
```
DDL raw CSVs (data/raw)
  │  ingest.py: chunked read, filter one state, per year
  ▼
data/interim/cases_<state>_<year>.parquet   (+ acts_<state>.parquet)
  │  ingest.py: join lookup keys, compute duration + censoring
  ▼
data/processed/cases_<state>.parquet        ← single source for all analysis
  │
  ├── notebooks (EDA, Kaplan-Meier, Cox)
  ├── features.py  → engineered features (e.g. court congestion at filing)
  └── models.py    → baseline / Cox / GBM survival, evaluation, saved model
                      │
                      ▼
                FastAPI /predict → survival curve JSON → demo front end
```

## Key definitions
- **duration_days** = `date_of_decision − date_of_filing` if decided,
  else `cutoff_date − date_of_filing` (cutoff = latest date observed in the data).
- **event** = 1 if decided, 0 if still pending (right-censored).
- Rows with impossible dates (decision before filing, dates outside 2000–cutoff) are flagged and
  excluded from modelling, with counts reported.

## Modules (`src/court_delay/`)
| Module | Responsibility |
|---|---|
| `config.py` | paths, expected column names, constants |
| `ingest.py` | raw → interim → processed survival table (CLI) |
| `features.py` | feature engineering (Week 4) |
| `models.py` | training, evaluation (C-index, IBS), persistence (Week 4) |
| `api/` | FastAPI app (Week 5) |

## Evaluation
- **Time-based split**: train on cases filed 2010–2015, test on 2016–2018 filings. Random splits leak
  court-level congestion information.
- Metrics: Harrell's / Uno's C-index, integrated Brier score; baseline must be reported alongside.
