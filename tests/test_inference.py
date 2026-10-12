"""The pandas-free API path (inference.py) predicts exactly what the training path does."""
import json

import numpy as np
import pandas as pd

from court_delay import models as M
from court_delay.inference import CoxModel


def _raw(n, seed):
    rng = np.random.default_rng(seed)
    raw = pd.DataFrame({
        "district_name": rng.choice(["Pune", "Thane", "Mumbai CMM Courts"], n),
        "judge_position": rng.choice(["civil court", "jmfc", "district court"], n),
        "case_category": rng.choice(["bail_remand", "civil_suit", "summary_criminal", "family"], n),
        "inflow_1y": rng.integers(5, 9000, n).astype(float),
        "backlog_2y": rng.integers(5, 9000, n).astype(float),
        "clearance_1y": np.where(rng.random(n) < 0.1, np.nan, rng.uniform(0, 1, n)),
    })
    raw["queue_ratio"] = raw["backlog_2y"] / raw["inflow_1y"]           # some above the cap
    raw["is_criminal"] = raw["case_category"].isin(["bail_remand", "summary_criminal"]).astype(float)
    return raw


def test_numpy_path_matches_pandas_path(tmp_path):
    raw = _raw(3000, 0)
    rng = np.random.default_rng(1)
    t = rng.exponential(300 / raw["queue_ratio"].clip(0.2, 4)).astype(int)
    c = rng.integers(0, 2000, len(raw))
    df = M.prepare(raw.assign(duration_days=np.minimum(t, c), event=(t <= c).astype(int)))
    model = M.XGBCox(rounds=40).fit(df.iloc[:2500], df.iloc[2500:])
    model.save(tmp_path)
    cats = {k: [str(v) for v in df[k].cat.categories] for k in M.CATEGORICAL}
    (tmp_path / "meta.json").write_text(json.dumps({"clearance_fill": 0.37, "categories": cats}))

    new = _raw(400, 2)
    new.loc[:9, "district_name"] = "Nowhere"                           # unknown category
    new.loc[10:19, "clearance_1y"] = np.nan
    want = M.prepare(new.copy(), clearance_fill=0.37, categories=cats)
    rows = new.astype(object).where(new.notna(), None).to_dict(orient="records")

    cm = CoxModel(tmp_path)
    X = cm.features(rows)
    np.testing.assert_array_equal(X[:, :len(M.NUMERIC)], want[M.NUMERIC].to_numpy(np.float32))
    np.testing.assert_allclose(cm.margin(X), model._margin(want), rtol=0, atol=1e-6)
    days = np.arange(0, 2000, 13)
    np.testing.assert_allclose(cm.survival(X, days), model.predict_survival(want, times=days), atol=1e-6)
    np.testing.assert_allclose(cm.shap(X), model.shap(want).to_numpy(), atol=1e-5)


def test_loads_binary_model_too(tmp_path):
    raw = _raw(800, 3)
    df = M.prepare(raw.assign(duration_days=np.arange(800) % 300, event=1))
    model = M.XGBCox(rounds=10).fit(df.iloc[:700], df.iloc[700:])
    model.save(tmp_path)
    cats = {k: [str(v) for v in df[k].cat.categories] for k in M.CATEGORICAL}
    (tmp_path / "meta.json").write_text(json.dumps({"clearance_fill": 0.5, "categories": cats}))
    X = CoxModel(tmp_path).features(raw.head(5).to_dict(orient="records"))
    before = CoxModel(tmp_path).margin(X)
    model.booster.save_model(tmp_path / "xgb_cox.ubj")
    (tmp_path / "xgb_cox.json").unlink()
    np.testing.assert_array_equal(CoxModel(tmp_path).margin(X), before)
