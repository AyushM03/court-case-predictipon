"""Prediction with numpy and XGBoost only: the API's runtime path (D-019).

Training builds features with pandas (`models.prepare`). The API predicts one court at a time and
must stay small enough for a Vercel function, so this module builds the same feature matrix
without pandas. `tests/test_inference.py` checks it matches the pandas path exactly.
"""
import json
import re
from pathlib import Path

import numpy as np

from court_delay.labels import COURT_SYSTEM_PATTERN, CRIMINAL

NUMERIC = ["log_inflow", "log_backlog", "queue_ratio", "clearance_1y", "clearance_missing",
           "is_criminal", "court_system"]
CATEGORICAL = ["case_category", "district_name", "judge_position"]
FEATURES = NUMERIC + CATEGORICAL
QUEUE_CAP = 5.0                              # queue ratios above this are capped (rare tiny courts)
MODEL_NAMES = ("xgb_cox.ubj", "xgb_cox.json")  # binary (smaller) first; training saves JSON
_court_system = re.compile(COURT_SYSTEM_PATTERN)


class CoxModel:
    """The saved XGBoost Cox model, its daily Breslow baseline and training metadata."""

    def __init__(self, folder: Path):
        import xgboost as xgb
        folder = Path(folder)
        self.booster = xgb.Booster()
        self.booster.load_model(next(folder / n for n in MODEL_NAMES if (folder / n).exists()))
        best = self.booster.attr("best_iteration")
        self.n_trees = int(best) + 1 if best is not None else self.booster.num_boosted_rounds()
        self.H0 = np.load(folder / "xgb_cox_H0.npy")
        self.meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        self.codes = {c: {v: i for i, v in enumerate(self.meta["categories"][c])} for c in CATEGORICAL}

    def features(self, rows: list[dict]) -> np.ndarray:
        """Feature matrix for rows with district_name, judge_position, case_category, inflow_1y,
        backlog_2y, queue_ratio and clearance_1y (None if unknown). Unknown category values
        become missing, as with pandas categoricals."""
        X = np.empty((len(rows), len(FEATURES)), np.float32)
        fill = self.meta["clearance_fill"]
        for i, r in enumerate(rows):
            clearance = r.get("clearance_1y")
            missing = clearance is None or clearance != clearance          # None or NaN
            X[i, :len(NUMERIC)] = [
                np.float32(np.log1p(float(r["inflow_1y"]))),
                np.float32(np.log1p(float(r["backlog_2y"]))),
                np.float32(min(float(r["queue_ratio"]), QUEUE_CAP)),
                np.float32(fill if missing else clearance),
                float(missing),
                float(r["case_category"] in CRIMINAL),
                float(bool(_court_system.match(str(r["district_name"])))),
            ]
            for j, c in enumerate(CATEGORICAL, start=len(NUMERIC)):
                X[i, j] = self.codes[c].get(str(r[c]), np.nan)
        return X

    def _dmatrix(self, X):
        import xgboost as xgb
        return xgb.DMatrix(X, feature_names=FEATURES, enable_categorical=True,
                           feature_types=["q"] * len(NUMERIC) + ["c"] * len(CATEGORICAL))

    def margin(self, X: np.ndarray) -> np.ndarray:
        return self.booster.predict(self._dmatrix(X), output_margin=True, iteration_range=(0, self.n_trees))

    def survival(self, X: np.ndarray, times: np.ndarray) -> np.ndarray:
        h0 = self.H0[np.minimum(np.asarray(times), len(self.H0) - 1)]
        return np.exp(-h0[None, :] * np.exp(self.margin(X))[:, None])

    def shap(self, X: np.ndarray) -> np.ndarray:
        """Exact TreeSHAP contributions (log hazard), one column per feature then the bias."""
        return self.booster.predict(self._dmatrix(X), pred_contribs=True, iteration_range=(0, self.n_trees))
