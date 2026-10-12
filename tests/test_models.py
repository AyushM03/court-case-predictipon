"""Survival helpers in models.py match lifelines, and the model wrappers return valid curves."""
import numpy as np
import pandas as pd
import pytest
from lifelines import CoxPHFitter, KaplanMeierFitter

from court_delay.models import (CATEGORICAL, GRID, KMBaseline, breslow, evaluate, km_curve, rmst,
                                split)


def _surv_data(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    t = rng.exponential(300 * np.exp(-0.7 * x)).astype(int)
    c = rng.integers(0, 1500, n)
    return x, np.minimum(t, c), (t <= c).astype(int)


def test_km_curve_matches_lifelines():
    _, d, e = _surv_data()
    times = np.array([0, 10, 100, 365, 900])
    km = KaplanMeierFitter().fit(d, e)
    np.testing.assert_allclose(km_curve(d, e, times), km.survival_function_at_times(times), atol=1e-10)


def test_km_curve_weights_equal_repeats():
    d, e, w = np.array([1, 3, 3, 7]), np.array([1, 0, 1, 1]), np.array([2, 1, 3, 1])
    times = np.arange(9)
    np.testing.assert_allclose(km_curve(d, e, times, w), km_curve(np.repeat(d, w), np.repeat(e, w), times))


def test_breslow_matches_lifelines():
    x, d, e = _surv_data()
    df = pd.DataFrame({"x": x, "T": d + 0.5, "E": e})
    cph = CoxPHFitter(baseline_estimation_method="breslow").fit(df, "T", "E")
    beta = cph.params_["x"]
    times = np.array([10, 100, 365, 900])
    # lifelines centres covariates: its baseline is at x = mean(x)
    ours = breslow(d, e, beta * (x - x.mean()), times)
    theirs = cph.baseline_cumulative_hazard_.reindex(times + 0.5, method="ffill").to_numpy().ravel()
    np.testing.assert_allclose(ours, theirs, rtol=1e-6)


def test_rmst_of_constant_one_is_horizon():
    assert rmst(np.ones((2, len(GRID))))[0] == GRID[-1]


def _cases(n=4000, seed=1):
    x, d, e = _surv_data(n, seed)
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"duration_days": d, "event": e, "year": rng.integers(2012, 2019, n),
                       "case_category": np.where(x > 0, "fast", "slow")})
    for c in CATEGORICAL[1:]:
        df[c] = "a"
    return df


def test_cox_predictions_keep_row_order():
    from court_delay.models import NUMERIC, CoxModel
    df = _cases(2000)
    rng = np.random.default_rng(2)
    for c in NUMERIC:
        df[c] = rng.normal(size=len(df))
    df["case_category"] = rng.choice(["a", "b"], len(df))
    df["log_inflow"] = -np.log(df["duration_days"] + 1) + rng.normal(0, 0.1, len(df))
    s = CoxModel().fit(df).predict_survival(df)
    # strong covariate: rows with larger log_inflow are shorter cases, so lower RMST
    assert np.corrcoef(rmst(s), df["log_inflow"])[0, 1] < -0.5


def test_split_by_filing_year():
    tr, te = split(_cases())
    assert tr["year"].between(2012, 2015).all() and te["year"].between(2016, 2018).all()


def test_baseline_curves_and_evaluation():
    df = _cases()
    tr, te = split(df)
    s = KMBaseline().fit(tr).predict_survival(te)
    assert s.shape == (len(te), len(GRID))
    assert (np.diff(s, axis=1) <= 1e-12).all() and s[:, 0].max() <= 1
    m = evaluate(s, te)
    assert 0.5 < m["c_uno"] < 1 and 0 < m["ibs"] < 0.25
    flat = evaluate(np.tile(s.mean(axis=0), (len(te), 1)), te)
    assert flat["c_uno"] == pytest.approx(0.5, abs=0.01)


def test_evaluate_short_follow_up():
    df = _cases()
    te = df[df["duration_days"] <= 400].copy()
    s = KMBaseline().fit(df).predict_survival(te)
    m = evaluate(s, te)
    assert m["horizon_days"] < 400 and np.isnan(m["brier_2y"]) and not np.isnan(m["brier_1y"])


def test_prepare_flags_court_systems_and_keeps_categories():
    from court_delay.models import prepare
    df = pd.DataFrame({"district_name": ["Pune", "Mumbai City Civil Court", None],
                       "judge_position": ["a", "b", "a"], "case_category": ["x", "x", "y"],
                       "is_criminal": pd.array([1, 0, None], dtype="Int8"),
                       "inflow_1y": [1.0, 2, 3], "backlog_2y": [1.0, 2, 3],
                       "queue_ratio": [1.0, 9, 1], "clearance_1y": [0.5, np.nan, 0.3]})
    out = prepare(df)
    assert out["court_system"].tolist() == [0, 1, 0]
    assert out["district_name"].tolist() == ["Pune", "Mumbai City Civil Court", "nan"]
    assert out["queue_ratio"].max() == 5 and out["clearance_missing"].tolist() == [0, 1, 0]


def _xgb_cases(n=3000, seed=3):
    from court_delay.models import NUMERIC
    df = _cases(n, seed)
    rng = np.random.default_rng(seed)
    for c in NUMERIC:
        df[c] = rng.normal(size=n).astype(np.float32)
    df["case_category"] = rng.choice(["x", "y", "z"], n)
    df["district_name"] = rng.choice(["p", "q"], n)
    for c in CATEGORICAL:
        df[c] = df[c].astype("category")
    return df


def test_xgb_cox_shap_sums_to_margin_and_roundtrips(tmp_path):
    from court_delay.models import XGBCox
    df = _xgb_cases()
    m = XGBCox(rounds=20).fit(df.iloc[:2500], df.iloc[2500:])
    sv = m.shap(df)
    np.testing.assert_allclose(sv.sum(axis=1), m._margin(df), rtol=1e-4, atol=1e-4)
    m.save(tmp_path)
    m2 = XGBCox.load(tmp_path)
    assert m2.booster.best_iteration == m.booster.best_iteration
    np.testing.assert_allclose(m2.predict_survival(df), m.predict_survival(df))


def test_median_days():
    from court_delay.models import median_days
    s = np.ones((3, len(GRID)))
    s[0, 4:] = 0.4                     # median at GRID[4]
    s[1, :] = 0.5                      # exactly 0.5 from day 0
    assert median_days(s)[0] == GRID[4] and median_days(s)[1] == 0 and np.isnan(median_days(s)[2])


def test_prepare_single_row_uses_training_categories():
    from court_delay.models import XGBCox, prepare
    df = _xgb_cases()
    df["court_system"] = 0.0           # derived columns, as prepare() would compute them
    df["clearance_missing"] = 0.0
    df["clearance_1y"] = df["clearance_1y"].abs()
    m = XGBCox(rounds=20).fit(df.iloc[:2500], df.iloc[2500:])
    cats = {c: list(df[c].cat.categories) for c in CATEGORICAL}
    # a lone row whose category would be code 0 on its own, but is not code 0 in training
    row = df[df["case_category"] == "z"].iloc[[0]].copy()
    raw = row.drop(columns=["log_inflow", "log_backlog", "clearance_missing", "court_system"]).assign(
        inflow_1y=np.expm1(row["log_inflow"]), backlog_2y=np.expm1(row["log_backlog"]))
    for c in CATEGORICAL:
        raw[c] = raw[c].astype(str)
    fresh = prepare(raw.copy(), clearance_fill=0.5, categories=cats)
    assert fresh["case_category"].cat.codes.iat[0] == cats["case_category"].index("z")
    np.testing.assert_allclose(m._margin(fresh), m._margin(row), rtol=1e-5)
    unknown = prepare(raw.assign(district_name="Nowhere").copy(), clearance_fill=0.5, categories=cats)
    assert unknown["district_name"].isna().all() and unknown["court_system"].iat[0] == 0
