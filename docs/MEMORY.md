# Project Memory

## Current status (2026-10-12)
- **Weeks 1–4 done.** Week 2's acts/sections chart is parked (needs the
  `acts_sections` download; A: has 3.2 GB free).
- **Observation now ends 2018-12-31 (D-016, replaces D-011).** Most records were last updated in
  mid-February 2019; later decisions are largely missing. Notebook 03 and all Week 3 numbers were
  re-run: KM median 536 days, districts 0.63× (Thane) to 1.81× (Gadchiroli), later filings ~2%
  faster per year.
- 10,059,428 Maharashtra cases (2010–2018) in `data/processed/cases_maharashtra.parquet`.
- `src/court_delay/features.py`: court congestion features per establishment (D-014), writes
  `model_maharashtra.parquet` (8.3M cases filed 2012–2018).
- `src/court_delay/models.py`: KM baseline, stratified Cox, XGBoost AFT, XGBoost Cox + Breslow, and
  `evaluate` (Uno C, integrated Brier up to 2 years, IPCW from the test set). D-015.
- `notebooks/04_models.ipynb` (~20 min): XGBoost Cox is best (C 0.699, IBS 0.188) but plain Cox is
  close (0.692, 0.188); baseline 0.651 / 0.200. Saved model: `data/models/xgb_cox.json` + `xgb_cox_H0.npy`.
- Calibration drifts: 2017–2018 filings are decided faster early on than predicted.
- `notebooks/05_shap.ipynb` (~2 min): exact TreeSHAP via `XGBCox.shap()`. Category 44% of |SHAP|,
  congestion ~30%, district 13%. Nagpur's speed is explained by light court load.
- Saved-model API: `XGBCox.load(DATA / "models")`, `.predict_survival(df)`, `.shap(df)`,
  `models.median_days(surv)`. Prepare request rows with `models.prepare`.
- RAM is tight (7.9 GB; other apps commit most of it). Load with `models.load()` (categoricals),
  sample, and `del` the full frames before fitting.

## API (Week 5, done)
- `python -m court_delay.train` (~8 min) writes `data/models/deploy/`: XGBoost Cox refit on all
  2012–2018 filings (1,002 trees, daily baseline to ~7 years), `meta.json` (training categories,
  clearance fill), and `courts.parquet` (632 active courts: name, district, judge position,
  congestion for a case filed 2019-01-01, categories heard). D-017.
- The evaluation model now lives in `data/models/eval/` (notebooks 04/05).
- `uvicorn court_delay.api:app`: `/health`, `/meta`, `/predict` (curve to 5 years, quartiles,
  P(decided by 1/2/3/5 years), SHAP explanation, rank among courts hearing that case type,
  warnings). First request ~2 s (model load), then ~0.3 s.

## Front end (Week 6, done)
- `frontend/`: React 18 + TypeScript + Vite + React Router (user asked for a component-based
  framework, not plain HTML/JS). Components: CourtPicker, StatTiles, DecisionCurve (own SVG,
  sizes to its container, hover tooltip, table view), Drivers (SHAP bars), Workload, Layout.
  Pages: Predict (selection in the URL) and Insights (figures 07–18 with captions).
- Dev: uvicorn on :8000 + `npm run dev` (Vite proxies /meta, /predict, /figures). Prod:
  `npm run build`; FastAPI serves `frontend/dist` with an index.html fallback for client routes.
- Checked with headless Chrome at 1280px and 500px (Chrome's minimum window width).

## Ship (Week 6)
- Notebook 02 re-run under D-016 (figures 01–06 now consistent; findings in docs/DATA.md).
- README has Results and Limitations sections and a Deployment section.
- `Dockerfile` + `.dockerignore` + `requirements-api.txt` (D-018): one container serving API,
  React app and figures. Built and tested locally (`docker build -t court-delay .`,
  `docker run -p 8000:8000 court-delay`); predictions match local exactly; image 594 MB after dropping pandas (D-019).

## Vercel (D-019)
- `vercel.json` with Services: `web` = frontend/ (static Vite), `api` = backend/ (FastAPI,
  `main:app`, `includeFiles: ../src/court_delay/**/*.py`). API is under `/api/*` everywhere now.
- `backend/model/` holds the exported model (`python -m court_delay.train --export backend/model`,
  UBJSON booster). It must be committed for GitHub deployments.
- `inference.py` predicts with numpy + XGBoost only; identical to the pandas path on all 12,008
  court × case-type rows. Function bundle 223 MB (limit for the fast path: 250 MB).
- Verified locally: `vercel build` (bundle contents and size, production route table) and
  `vercel dev -L` (API through the router; figures only fail in dev mode). Tools for this live in
  the session scratchpad (Vercel CLI 63.1.2, uv), not in the repo.

## Live (D-020)
- **https://court-delay.onrender.com**: Render free plan, Docker (`render.yaml` Blueprint),
  redeploys on every push to `main`. The image uses the committed `backend/model/`.
- Checked 2026-10-12: `/`, `/insights`, `/api/health`, `/api/meta`, `/api/docs`, figures, and a
  prediction (same numbers as local). Sleeps after ~15 min idle; wake-up takes about a minute.
- Vercel (D-019) is configured but not used: the build passed, the upload step failed.

## Next step
Project complete. Optional extensions: acts/sections chart (needs `acts_sections` download),
competing risks for transfers and Lok Adalat referrals.

## Open questions
- ~~COVID structural break~~: superseded. The data freezes in Feb 2019; observation ends 2018-12-31 (D-016).
- ~~Cases with a disposition but no date~~: resolved. Only 1,717 cases (0.02%) are real ones,
  and they stay censored.
- Transferred and Lok Adalat referrals (~11% of decisions) count as events for now (D-005).
  Competing risks is still an option for a later extension.
- `acts_sections` has not been downloaded yet. It comes after the cases in the zip and is large.
  Needs a disk-space check first.

- ~~112k cases pending 9+ years~~: resolved, they are live (still heard) and stay censored (D-012).
- Eight `district_name` values are court systems, not districts. Handle them as their own
  group in models.

## Archive
Unrelated "Agent Action Firewall" planning docs moved to `_archive/agent-action-firewall/`.
