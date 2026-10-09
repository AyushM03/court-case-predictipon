# Tasks

## Week 1 — Shrink the problem
- [x] Project structure, docs, requirements
- [x] Ingest script: state filter, key joins, duration + censoring (tested on synthetic data)
- [x] Download DDL keys + cases (`court_delay.fetch`; all years in `cases.tar.gz`)
- [x] Run ingest on 2010 only; confirm column names match `config.py` (they do)
- [x] Run for all years 2010–2018 (10.06M cases)
- [x] `notebooks/01_explore.ipynb`: what each column means, null rates, code→name joins, fill docs/DATA.md

## Week 2 — EDA
- [x] Map 1,160 type labels → `case_category` + civil/criminal flag
- [ ] Duration distributions (decided cases) + share pending by filing year
- [ ] Slowest districts / courts; civil vs criminal; slowest acts & sections
- [ ] Trends 2010–2018
- [ ] 5–6 clean charts saved to reports/figures

## Week 3 — Survival analysis
- [ ] Kaplan-Meier: overall, by case category, by district (lifelines)
- [ ] Log-rank tests between groups
- [ ] Cox PH model; check proportional hazards assumption
- [ ] Write a plain-English explanation of censoring (README section)

## Week 4 — Prediction
- [ ] Baseline: median duration by case type (KM median)
- [ ] Feature: court congestion at filing (pending cases in that court on the filing date)
- [ ] Cox PH with full features
- [ ] Gradient-boosted survival model (scikit-survival GBSA or XGBoost AFT)
- [ ] Compare on C-index + integrated Brier score, time-based split
- [ ] SHAP explanations

## Weeks 5–6 — Ship
- [ ] FastAPI `/predict` returning survival curve; `/meta` for dropdowns
- [ ] Front end: district/case type pickers + curve; insights page
- [ ] Deploy; final README with results
