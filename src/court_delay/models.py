"""Week 4 prediction models on the congestion table (D-015).

Every model returns survival probabilities on the day grid GRID, so all of them are evaluated the
same way: Uno's IPCW C-index on -RMST up to TAU and the integrated Brier score.

- KMBaseline     Kaplan-Meier curve of the case's category
- CoxModel       lifelines Cox, stratified by case_category
- XGBAFT         XGBoost accelerated failure time (log-normal)
- XGBCox         XGBoost Cox partial likelihood + Breslow baseline
"""
import numpy as np
import pandas as pd

from court_delay import config as C
from court_delay.survival import is_court_system

TRAIN_YEARS = (2012, 2015)
TEST_YEARS = (2016, 2018)
TAU = 730                                    # evaluate up to 2 years (test follow-up ends 2018-12-31)
GRID = np.arange(0, TAU + 1, 15)             # days at which models predict S(t)
BRIER_TIMES = GRID[(GRID >= 30)]
from court_delay.inference import CATEGORICAL, NUMERIC, QUEUE_CAP  # noqa: E402  (one definition)
MIN_LEVEL = 2000                             # rarer judge_position levels -> "other"


def load(path=None) -> pd.DataFrame:
    """Model table with only the model columns, strings as categories (keeps RAM down)."""
    path = path or C.PROCESSED / C.MODEL_FILE
    cols = ["year", "district_name", "judge_position", "case_category", "is_criminal",
            "duration_days", "event", "inflow_1y", "backlog_2y", "queue_ratio", "clearance_1y"]
    import pyarrow.parquet as pq          # training only; the API never loads the table
    df = pq.read_table(path, columns=cols).to_pandas(strings_to_categorical=True)
    return prepare(df)


def prepare(df: pd.DataFrame, clearance_fill=None, categories=None) -> pd.DataFrame:
    """Model features from the congestion table. For new rows (the API) pass the training
    `clearance_fill` and `categories` ({column: training category list}): XGBoost reads
    categoricals by their codes, so a request must use exactly the training categories."""
    df["log_inflow"] = np.log1p(df.pop("inflow_1y")).astype(np.float32)
    df["log_backlog"] = np.log1p(df.pop("backlog_2y")).astype(np.float32)
    df["queue_ratio"] = df["queue_ratio"].clip(upper=QUEUE_CAP).astype(np.float32)
    df["clearance_missing"] = df["clearance_1y"].isna().astype(np.float32)
    fill = df["clearance_1y"].median() if clearance_fill is None else clearance_fill
    df["clearance_1y"] = df["clearance_1y"].fillna(fill).astype(np.float32)
    df["is_criminal"] = df["is_criminal"].fillna(0).astype(np.float32)
    for c in CATEGORICAL:                    # work on category labels, never 8M strings (RAM)
        if categories is not None:
            df[c] = pd.Categorical(df[c].astype(str), categories=categories[c])
            continue
        if not isinstance(df[c].dtype, pd.CategoricalDtype):
            df[c] = df[c].astype("category")
        if df[c].isna().any():
            df[c] = df[c].cat.add_categories("nan").fillna("nan")
        df[c] = df[c].cat.rename_categories(df[c].cat.categories.astype(str))
    dist = df["district_name"].cat
    flag = np.append(is_court_system(pd.Series(dist.categories, dtype=str)).to_numpy(np.float32), 0)
    df["court_system"] = flag[dist.codes.to_numpy()]          # code -1 (unknown) -> last entry, 0
    return df


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = df["year"].between(*TRAIN_YEARS)
    te = df["year"].between(*TEST_YEARS)
    return df[tr].reset_index(drop=True), df[te].reset_index(drop=True)


def km_curve(durations, events, times, weights=None) -> np.ndarray:
    """Kaplan-Meier S(t) at integer `times` (S includes events on day t). Durations in whole days."""
    durations = np.asarray(durations, np.int64)
    w = np.ones(len(durations)) if weights is None else np.asarray(weights, float)
    m = max(int(durations.max()), int(np.max(times))) + 1
    d = np.bincount(durations, weights=w * np.asarray(events), minlength=m)
    c = np.bincount(durations, weights=w, minlength=m)
    at_risk = w.sum() - np.cumsum(c) + c
    h = np.divide(d, at_risk, out=np.zeros(m), where=at_risk > 0)
    return np.cumprod(1 - h)[np.asarray(times)]


def rmst(surv: np.ndarray, grid=GRID) -> np.ndarray:
    """Restricted mean survival time up to grid[-1] from S on `grid` (step function)."""
    return (surv[:, :-1] * np.diff(grid)).sum(axis=1)


class KMBaseline:
    """Predict each case's category KM curve."""

    def fit(self, df):
        self.curves = {cat: km_curve(g["duration_days"], g["event"], GRID)
                       for cat, g in df.groupby("case_category", observed=True)}
        self.overall = km_curve(df["duration_days"], df["event"], GRID)
        return self

    def predict_survival(self, df):
        out = np.empty((len(df), len(GRID)))
        cats = df["case_category"].astype(str).to_numpy()
        for cat in np.unique(cats):
            out[cats == cat] = self.curves.get(cat, self.overall)
        return out


class CoxModel:
    """lifelines Cox stratified by case_category; district and judge_position one-hot."""

    def __init__(self, penalizer=1e-3):
        self.penalizer = penalizer

    def _design(self, df):
        X = df[NUMERIC].astype(float).copy()
        X = (X - self.mu) / self.sd
        for c in ["district_name", "judge_position"]:
            v = df[c].astype(str).where(df[c].astype(str).isin(self.levels[c]), "other")
            for lev in self.levels[c][1:]:                 # first level is the reference
                X[f"{c}={lev}"] = (v == lev).astype(float)
        X["case_category"] = df["case_category"].astype(str).to_numpy()
        return X

    def fit(self, df):
        from lifelines import CoxPHFitter
        num = df[NUMERIC].astype(float)
        self.mu, self.sd = num.mean(), num.std().replace(0, 1)
        self.levels = {}
        for c in ["district_name", "judge_position"]:
            vc = df[c].astype(str).value_counts()
            self.levels[c] = list(vc.index[vc >= MIN_LEVEL]) + (["other"] if (vc < MIN_LEVEL).any() else [])
        X = self._design(df)
        X["duration_days"] = df["duration_days"].to_numpy() + 0.5   # lifelines needs > 0
        X["event"] = df["event"].to_numpy()
        self.cph = CoxPHFitter(penalizer=self.penalizer)
        self.cph.fit(X, "duration_days", "event", strata=["case_category"])
        return self

    def predict_survival(self, df):
        X = self._design(df)
        sf = self.cph.predict_survival_function(X, times=GRID + 0.5)
        return sf[X.index].to_numpy().T       # stratified predictions come back grouped by stratum


def _xgb_matrix(df):
    import xgboost as xgb
    return xgb.DMatrix(df[NUMERIC + CATEGORICAL], enable_categorical=True, nthread=-1)


XGB_PARAMS = {"tree_method": "hist", "eta": 0.1, "max_depth": 8, "min_child_weight": 50,
              "subsample": 0.8, "colsample_bytree": 0.8, "max_cat_to_onehot": 1, "nthread": -1}


class XGBAFT:
    """XGBoost AFT on log(duration + 1) with a normal error (log-normal survival)."""

    def __init__(self, sigma=1.2, rounds=1000):
        self.sigma, self.rounds = sigma, rounds

    def _dmatrix(self, df):
        d = _xgb_matrix(df)
        y = df["duration_days"].to_numpy(float) + 1
        d.set_float_info("label_lower_bound", y)
        d.set_float_info("label_upper_bound", np.where(df["event"].to_numpy() == 1, y, np.inf))
        return d

    def fit(self, df, valid):
        import xgboost as xgb
        params = XGB_PARAMS | {"objective": "survival:aft", "eval_metric": "aft-nloglik",
                               "aft_loss_distribution": "normal",
                               "aft_loss_distribution_scale": self.sigma}
        dv = self._dmatrix(valid)
        self.booster = xgb.train(params, self._dmatrix(df), self.rounds, evals=[(dv, "valid")],
                                 early_stopping_rounds=30, verbose_eval=False)
        return self

    def predict_survival(self, df):
        mu = self.booster.predict(_xgb_matrix(df), output_margin=True,
                                  iteration_range=(0, self.booster.best_iteration + 1))
        z = (np.log(GRID + 1.0)[None, :] - mu[:, None]) / self.sigma
        from scipy.stats import norm
        return norm.sf(z)


class XGBCox:
    """XGBoost Cox partial likelihood; S(t|x) = exp(-H0(t) e^f(x)) with a Breslow H0.

    H0 is kept for every day up to the longest training duration, so curves can be read at any
    horizon the training data covers (the API uses up to 5 years)."""

    def __init__(self, rounds=1000):
        self.rounds = rounds

    def _dmatrix(self, df):
        d = _xgb_matrix(df)
        y = df["duration_days"].to_numpy(float) + 1
        d.set_label(np.where(df["event"].to_numpy() == 1, y, -y))
        return d

    def fit(self, df, valid):
        import xgboost as xgb
        params = XGB_PARAMS | {"objective": "survival:cox", "eval_metric": "cox-nloglik"}
        dv = self._dmatrix(valid)
        self.booster = xgb.train(params, self._dmatrix(df), self.rounds, evals=[(dv, "valid")],
                                 early_stopping_rounds=30, verbose_eval=False)
        self.set_baseline(df)
        return self

    def _margin(self, df):
        return self.booster.predict(_xgb_matrix(df), output_margin=True,
                                    iteration_range=(0, self.booster.best_iteration + 1))

    def set_baseline(self, df):
        """Daily Breslow baseline from the training rows `df`."""
        days = np.arange(int(df["duration_days"].max()) + 1)
        self.H0 = breslow(df["duration_days"], df["event"], self._margin(df), days)
        return self

    def predict_survival(self, df, times=GRID):
        h0 = self.H0[np.minimum(np.asarray(times), len(self.H0) - 1)]
        return np.exp(-h0[None, :] * np.exp(self._margin(df))[:, None])

    def shap(self, df) -> pd.DataFrame:
        """Exact TreeSHAP contributions to the log hazard, one column per feature plus `bias`.
        Each row sums to the model margin. Positive = higher hazard = decided sooner."""
        c = self.booster.predict(_xgb_matrix(df), pred_contribs=True,
                                 iteration_range=(0, self.booster.best_iteration + 1))
        return pd.DataFrame(c, columns=NUMERIC + CATEGORICAL + ["bias"], index=df.index)

    def save(self, folder):
        self.booster.set_attr(best_iteration=str(self.booster.best_iteration))
        self.booster.save_model(folder / "xgb_cox.json")
        np.save(folder / "xgb_cox_H0.npy", self.H0)

    @classmethod
    def load(cls, folder):
        import xgboost as xgb
        m = cls()
        m.booster = xgb.Booster()
        m.booster.load_model(folder / "xgb_cox.json")
        best = m.booster.attr("best_iteration")
        m.booster.best_iteration = int(best) if best is not None else m.booster.num_boosted_rounds() - 1
        m.H0 = np.load(folder / "xgb_cox_H0.npy")
        return m


def median_days(surv: np.ndarray, grid=GRID) -> np.ndarray:
    """First grid day where S(t) <= 0.5; NaN when the median lies beyond the grid."""
    below = surv <= 0.5
    return np.where(below.any(axis=1), grid[below.argmax(axis=1)].astype(float), np.nan)


def breslow(durations, events, margin, times) -> np.ndarray:
    """Breslow cumulative baseline hazard at `times` for log-hazard `margin`."""
    durations = np.asarray(durations, np.int64)
    m = max(int(durations.max()), int(np.max(times))) + 1
    r = np.exp(np.asarray(margin, float))
    risk = np.bincount(durations, weights=r, minlength=m)[::-1].cumsum()[::-1]  # sum over T >= t
    d = np.bincount(durations, weights=np.asarray(events, float), minlength=m)
    dH = np.divide(d, risk, out=np.zeros(m), where=risk > 0)
    return np.cumsum(dH)[np.asarray(times)]


def surv_array(df):
    from sksurv.util import Surv
    return Surv.from_arrays(df["event"].to_numpy() == 1, df["duration_days"].to_numpy(float))


def evaluate(surv: np.ndarray, test: pd.DataFrame) -> dict:
    """Uno's C (risk = -RMST up to TAU), Harrell's C, integrated Brier on [30, TAU], Brier at 1y/2y.

    The censoring distribution for IPCW is estimated on the test set itself: test filings are
    much more heavily censored than training ones. For a test set with shorter follow-up (one late
    filing year) the horizon shrinks to the follow-up seen, and Brier scores past it are NaN.
    """
    from sksurv.metrics import (brier_score, concordance_index_censored, concordance_index_ipcw,
                                integrated_brier_score)
    y = surv_array(test)
    horizon = min(TAU, y["time"].max() - 1)
    times = BRIER_TIMES[BRIER_TIMES < horizon]
    risk = -rmst(surv)
    t_idx = np.searchsorted(GRID, times)
    _, b = brier_score(y, y, surv[:, t_idx], times)
    at = lambda d: b[times == d][0] if (times == d).any() else np.nan
    return {
        "c_uno": concordance_index_ipcw(y, y, risk, tau=horizon)[0],
        "c_harrell": concordance_index_censored(y["event"], y["time"], risk)[0],
        "ibs": integrated_brier_score(y, y, surv[:, t_idx], times),
        "brier_1y": at(360),
        "brier_2y": at(720),
        "horizon_days": float(horizon),
    }
