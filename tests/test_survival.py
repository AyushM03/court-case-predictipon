"""Administrative censoring and aggregation used by the survival models."""
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter

from court_delay.survival import aggregate, censor_at, is_court_system


def _cases():
    return pd.DataFrame({
        "filing_date": pd.to_datetime(["2019-01-01", "2019-01-01", "2020-01-01", "2020-01-01"]),
        "duration_days": [100, 500, 30, 200],
        "event": [1, 1, 0, 1],
    })


def test_censor_at_cuts_late_decisions_and_follow_up():
    out = censor_at(_cases(), "2020-03-15")
    # decided before the date: unchanged
    assert out.loc[0, ["duration_days", "event"]].tolist() == [100, 1]
    # decided after the date: censored at the date
    assert out.loc[1, ["duration_days", "event"]].tolist() == [439, 0]
    # still censored, follow-up shortened if it ran past the date
    assert out.loc[2, ["duration_days", "event"]].tolist() == [30, 0]
    assert out.loc[3, ["duration_days", "event"]].tolist() == [74, 0]


def test_censor_at_leaves_input_untouched():
    df = _cases()
    censor_at(df, "2019-02-01")
    assert df["event"].tolist() == [1, 1, 0, 1]


def test_aggregate_gives_same_km_as_raw():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"duration_days": rng.integers(0, 50, 2000),
                       "event": rng.integers(0, 2, 2000), "g": rng.integers(0, 3, 2000)})
    agg = aggregate(df, "g")
    assert agg["n"].sum() == len(df)
    raw = KaplanMeierFitter().fit(df.duration_days, df.event).survival_function_
    w = KaplanMeierFitter().fit(agg.duration_days, agg.event, weights=agg.n).survival_function_
    np.testing.assert_allclose(raw.values, w.values)


def test_is_court_system():
    s = pd.Series(["Pune", "Mumbai CMM Courts", "Maharashtra Industrial Court", None])
    assert is_court_system(s).tolist() == [False, True, True, False]
