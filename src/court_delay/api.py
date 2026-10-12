"""FastAPI service: predicted time to decision for a case type in a given court (D-017).

    uvicorn court_delay.api:app --reload         # docs at http://127.0.0.1:8000/api/docs

All endpoints live under /api, the same locally, in Docker and on Vercel (D-019):
GET  /api/health    model and data status
GET  /api/meta      districts, their courts, and the case categories each court hears (dropdowns)
POST /api/predict   {"court_id": "25-3", "case_category": "civil_suit"} -> curve, quantiles, explanation

Locally and in Docker it also serves the built React front end (frontend/dist) at / and the report
figures at /figures. On Vercel the front end is a separate static service (backend/main.py).

Predictions are for a case filed on the snapshot date (2019-01-01), under the court's congestion
at that time. They describe how long courts take, not who wins (D-006).
"""
import json
from functools import cached_property
from itertools import groupby

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from court_delay.config import DEPLOY, ROOT
from court_delay.inference import FEATURES, MODEL_NAMES, CoxModel
from court_delay.labels import CRIMINAL

FRONTEND = ROOT / "frontend" / "dist"      # `npm run build` in frontend/
FIGURES = ROOT / "reports" / "figures"

MODEL_FILES = ("xgb_cox_H0.npy", "meta.json", "courts.json")   # plus one of inference.MODEL_NAMES
HORIZON_DAYS = 1825                     # curves to 5 years (the baseline is estimated to ~7)
CURVE_STEP = 7
CATEGORY_LABELS = {
    "bail_remand": "Bail / remand application", "criminal_misc": "Criminal miscellaneous",
    "summary_criminal": "Summary / summons criminal case", "regular_criminal": "Regular (warrant) criminal case",
    "sessions_special": "Sessions / special court case", "criminal_appeal_revision": "Criminal appeal / revision",
    "juvenile": "Juvenile justice", "domestic_violence": "Domestic violence",
    "civil_suit": "Civil suit", "civil_misc": "Civil miscellaneous", "civil_appeal_revision": "Civil appeal / revision",
    "execution": "Execution petition", "family": "Family / matrimonial", "succession": "Succession / probate",
    "motor_accident": "Motor accident claim", "labour": "Labour / industrial dispute",
    "land_acquisition": "Land acquisition reference", "arbitration_cooperative": "Arbitration / co-operative dispute",
    "other": "Other",
}
FEATURE_LABELS = {
    "case_category": "Case type", "district_name": "District", "judge_position": "Court level",
    "queue_ratio": "Queue ratio (backlog ÷ yearly inflow)", "clearance_1y": "Clearance rate",
    "log_inflow": "New filings, past year", "log_backlog": "Pending cases filed in past 2 years",
    "is_criminal": "Criminal case", "court_system": "Mumbai / statewide court system",
    "clearance_missing": "Clearance rate unknown",
}
NOTE = ("Statistical estimate from Maharashtra district court records, 2010–2018 (Development Data "
        "Lab). Describes how long similar cases took, not the outcome of any case. Not legal advice.")


class PredictRequest(BaseModel):
    court_id: str = Field(examples=["25-3"])
    case_category: str = Field(examples=["civil_suit"])


class CurvePoint(BaseModel):
    day: int
    decided: float = Field(description="probability the case is decided by this day")


class Contribution(BaseModel):
    feature: str
    label: str
    value: str
    multiplier: float = Field(description="effect on the decision rate; above 1 = decided sooner")


class Court(BaseModel):
    court_id: str
    court_name: str
    district: str
    judge_position: str
    categories: list[str]


class Congestion(BaseModel):
    inflow_1y: int
    backlog_2y: int
    queue_ratio: float
    clearance_1y: float | None


class Comparison(BaseModel):
    courts_hearing_category: int
    statewide_median_days: float | None
    share_of_courts_slower: float = Field(description="share of those courts with a longer median")


class Prediction(BaseModel):
    court: Court
    case_category: str
    case_category_label: str
    congestion: Congestion
    median_days: float | None = Field(description="null when the median is beyond the horizon")
    quartile_days: list[float | None] = Field(description="days by which 25% / 50% / 75% are decided")
    decided_by: dict[str, float] = Field(description="probability decided within 1, 2, 3 and 5 years")
    curve: list[CurvePoint]
    explanation: list[Contribution]
    comparison: Comparison
    warnings: list[str]
    snapshot_date: str
    note: str


class Predictor:
    """Loads the deployment model and court table lazily from `folder`. Uses numpy only
    (inference.py), so the API needs no pandas (D-019)."""

    def __init__(self, folder=DEPLOY):
        self.folder = folder
        self._medians = {}

    @cached_property
    def model(self) -> CoxModel:
        return CoxModel(self.folder)

    @property
    def meta(self):
        return self.model.meta

    @cached_property
    def courts(self) -> dict[str, dict]:
        """court_id -> court record, in file order (sorted by district, then court name)."""
        rows = json.loads((self.folder / "courts.json").read_text(encoding="utf-8"))
        return {r["court_id"]: r for r in rows}

    def court(self, court_id) -> dict:
        if court_id not in self.courts:
            raise HTTPException(404, f"unknown court_id {court_id!r}; see /api/meta")
        return self.courts[court_id]

    def rows(self, courts: list[dict], category: str) -> np.ndarray:
        """Feature matrix for `category` in each of `courts`."""
        return self.model.features([{**c, "case_category": category} for c in courts])

    def predict(self, court_id: str, category: str) -> Prediction:
        if category not in self.meta["categories"]["case_category"]:
            raise HTTPException(422, f"unknown case_category {category!r}; see /api/meta")
        c = self.court(court_id)
        X = self.rows([c], category)
        days = np.arange(HORIZON_DAYS + 1)
        decided = 1 - self.model.survival(X, days)[0]
        q = [_first_day(decided, p) for p in (0.25, 0.5, 0.75)]

        clearance = c["clearance_1y"]
        sv = self.model.shap(X)[0, :len(FEATURES)]
        shown = {"log_inflow": f"{c['inflow_1y']:,.0f}", "log_backlog": f"{c['backlog_2y']:,.0f}",
                 "queue_ratio": f"{c['queue_ratio']:.2f}",
                 "clearance_1y": "unknown" if clearance is None else f"{clearance:.0%}",
                 "case_category": CATEGORY_LABELS.get(category, category),
                 "district_name": c["district_name"], "judge_position": c["judge_position"],
                 "is_criminal": "yes" if category in CRIMINAL else "no",
                 "court_system": "yes" if X[0, FEATURES.index("court_system")] else "no",
                 "clearance_missing": "yes" if clearance is None else "no"}
        explanation = [Contribution(feature=FEATURES[i], label=FEATURE_LABELS[FEATURES[i]],
                                    value=shown[FEATURES[i]], multiplier=round(float(np.exp(sv[i])), 3))
                       for i in np.argsort(-np.abs(sv), kind="stable")]

        warnings = []
        if category not in c["categories"]:
            warnings.append(f"This court rarely hears {CATEGORY_LABELS.get(category, category).lower()} "
                            "cases (fewer than 20 filed 2016–2018); treat the estimate with caution.")
        return Prediction(
            court=_court(c), case_category=category,
            case_category_label=CATEGORY_LABELS.get(category, category),
            congestion=Congestion(inflow_1y=int(c["inflow_1y"]), backlog_2y=int(c["backlog_2y"]),
                                  queue_ratio=round(float(c["queue_ratio"]), 3),
                                  clearance_1y=None if clearance is None else round(float(clearance), 3)),
            median_days=q[1], quartile_days=q,
            decided_by={f"{y}y": round(float(decided[min(y * 365, HORIZON_DAYS)]), 4) for y in (1, 2, 3, 5)},
            curve=[CurvePoint(day=int(d), decided=round(float(decided[d]), 4))
                   for d in days[::CURVE_STEP]],
            explanation=explanation, comparison=self.compare(category, q[1]), warnings=warnings,
            snapshot_date=self.meta["snapshot_date"], note=NOTE,
        )

    def category_medians(self, category: str) -> np.ndarray:
        """Predicted median of every court that hears `category` (inf beyond the horizon).
        Independent of the requested court, so it is computed once per category."""
        if category not in self._medians:
            hearing = [c for c in self.courts.values() if category in c["categories"]]
            meds = np.array([], dtype=float)
            if hearing:
                days = np.arange(HORIZON_DAYS + 1)
                decided = 1 - self.model.survival(self.rows(hearing, category), days)
                meds = np.array([_first_day(d, 0.5) for d in decided], dtype=float)
            self._medians[category] = np.where(np.isnan(meds), np.inf, meds)
        return self._medians[category]

    def compare(self, category: str, median: float | None) -> Comparison:
        """Where this court's median sits among all courts that hear `category`."""
        meds = self.category_medians(category)
        if len(meds) == 0:
            return Comparison(courts_hearing_category=0, statewide_median_days=None, share_of_courts_slower=0)
        mine = np.inf if median is None else median
        mid = float(np.median(meds))
        return Comparison(courts_hearing_category=len(meds),
                          statewide_median_days=None if np.isinf(mid) else mid,
                          share_of_courts_slower=round(float((meds > mine).mean()), 3))


def _first_day(decided: np.ndarray, p: float) -> float | None:
    hit = np.flatnonzero(decided >= p)
    return float(hit[0]) if len(hit) else None


def _court(c: dict) -> Court:
    return Court(court_id=c["court_id"], court_name=c["court_name"], district=c["district_name"],
                 judge_position=c["judge_position"], categories=list(c["categories"]))


def create_app(folder=DEPLOY, frontend=FRONTEND) -> FastAPI:
    app = FastAPI(title="How Slow Is Justice?", version="0.1.0",
                  description="Predicted time to decision in Maharashtra district courts.",
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    pred = Predictor(folder)
    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health():
        ok = (all((folder / f).exists() for f in MODEL_FILES)
              and any((folder / f).exists() for f in MODEL_NAMES))
        return {"status": "ok" if ok else "missing model files", "model_dir": str(folder)}

    @api.get("/meta")
    def meta():
        by_district = sorted(pred.courts.values(), key=lambda c: c["district_name"])  # stable
        districts = [{"district": d, "courts": [_court(c).model_dump() for c in g]}
                     for d, g in groupby(by_district, key=lambda c: c["district_name"])]
        cats = [{"id": k, "label": CATEGORY_LABELS.get(k, k), "criminal": k in CRIMINAL}
                for k in pred.meta["categories"]["case_category"]]
        return {"districts": districts, "case_categories": cats,
                "snapshot_date": pred.meta["snapshot_date"], "horizon_days": HORIZON_DAYS,
                "trained_on": pred.meta["trained_on"], "note": NOTE}

    @api.post("/predict", response_model=Prediction)
    def predict(req: PredictRequest):
        return pred.predict(req.court_id, req.case_category)

    app.include_router(api)
    if FIGURES.exists():
        app.mount("/figures", StaticFiles(directory=FIGURES), name="figures")
    if frontend is not None and (frontend / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            """Serve the React app; unknown paths get index.html so client routes work."""
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "unknown API route; see /api/docs")
            f = (frontend / path).resolve()
            if path and f.is_file() and f.is_relative_to(frontend.resolve()):
                return FileResponse(f)
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
