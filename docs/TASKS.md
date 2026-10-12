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
- [x] Duration distributions (decided cases) + share pending by filing year
- [x] Slowest districts / courts; civil vs criminal
- [ ] Slowest acts & sections (needs `acts_sections` download + disk check; parked, A: has 3.2 GB free)
- [x] Trends 2010–2018
- [x] 5–6 clean charts saved to reports/figures

## Week 3 — Survival analysis
- [x] Kaplan-Meier: overall, by case category, by district (lifelines)
- [x] Log-rank tests between groups
- [x] Cox PH model; check proportional hazards assumption
- [x] Write a plain-English explanation of censoring (README section)

## Week 4 — Prediction
- [x] Baseline: KM curve by case category (C 0.651)
- [x] Feature: court congestion at filing (`features.py`: inflow, 2-year backlog, queue ratio, clearance; D-014)
- [x] Cox PH with full features, stratified by category (C 0.692)
- [x] Gradient-boosted survival model: XGBoost Cox (C 0.699, best) and AFT
- [x] Compare on C-index + integrated Brier score, time-based split (`notebooks/04_models.ipynb`, D-015)
- [x] SHAP explanations (`notebooks/05_shap.ipynb`: exact TreeSHAP, figures 14–18)

## Weeks 5–6 — Ship
- [x] FastAPI `/predict` returning survival curve; `/meta` for dropdowns (`api.py`, `train.py`; D-017)
- [x] Front end: district/case type pickers + curve; insights page (React + TypeScript, `frontend/`)
- [x] Final README with results
- [x] Deployable container (`Dockerfile`, D-018), tested locally
- [x] Vercel setup (Services: static app + Python API, D-019), verified with `vercel build` and `vercel dev`
- [ ] Deploy to Vercel (the user's account: GitHub import or `npx vercel --prod`)
