"""Court congestion features match a brute-force count."""
import numpy as np
import pytest
import pandas as pd

from court_delay.features import BACKLOG_DAYS, INFLOW_DAYS, add_congestion


def _random_cases(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "dist_code": rng.integers(1, 3, n),
        "court_no": rng.integers(1, 4, n),
        "filing_date": pd.Timestamp("2010-01-01") + pd.to_timedelta(rng.integers(0, 2000, n), unit="D"),
        "duration_days": rng.integers(0, 900, n),
        "event": rng.integers(0, 2, n),
    })


def _brute(df):
    f = (df.filing_date - pd.Timestamp("2000-01-01")).dt.days.to_numpy()
    end = np.where(df.event == 1, f + df.duration_days, np.inf)
    court = list(zip(df.dist_code, df.court_no))
    rows = []
    for i in range(len(df)):
        t = f[i]
        same = np.array([c == court[i] for c in court])
        b = same & (f >= t - BACKLOG_DAYS) & (f < t)
        inflow = (same & (f >= t - INFLOW_DAYS) & (f < t)).sum()
        cohort = same & (f >= t - BACKLOG_DAYS) & (f < t - INFLOW_DAYS)
        clear = (cohort & (end < t)).sum() / cohort.sum() if cohort.sum() else np.nan
        rows.append((inflow, (b & (end >= t)).sum(), clear))
    return pd.DataFrame(rows, columns=["inflow_1y", "backlog_2y", "clearance_1y"])


def test_matches_brute_force():
    df = _random_cases()
    got = add_congestion(df)[["inflow_1y", "backlog_2y", "clearance_1y"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(got, _brute(df), check_dtype=False)


def test_same_day_filings_not_counted():
    df = pd.DataFrame({"dist_code": 1, "court_no": 1,
                       "filing_date": pd.to_datetime(["2015-01-01"] * 3),
                       "duration_days": [0, 5, 10], "event": 1})
    out = add_congestion(df)
    assert out["inflow_1y"].tolist() == [0, 0, 0]
    assert out["backlog_2y"].tolist() == [0, 0, 0]


def test_decided_case_leaves_backlog():
    df = pd.DataFrame({"dist_code": 1, "court_no": 1,
                       "filing_date": pd.to_datetime(["2015-01-01", "2015-03-01", "2015-06-01"]),
                       "duration_days": [100, 400, 0], "event": [1, 1, 0]})
    out = add_congestion(df)
    # On 2015-06-01: case 1 was decided on day 100 (2015-04-11), case 2 is still pending.
    assert out.loc[2, "backlog_2y"] == 1
    assert out.loc[2, "inflow_1y"] == 2


def test_court_snapshot_matches_a_case_filed_that_day():
    from court_delay.features import court_snapshot
    df = _random_cases()
    date = pd.Timestamp("2014-06-01")
    snap = court_snapshot(df, date).set_index(["dist_code", "court_no"])
    assert len(snap) == df.groupby(["dist_code", "court_no"]).ngroups
    probe = pd.DataFrame({"dist_code": [1], "court_no": [2], "filing_date": [date],
                          "duration_days": [0], "event": [0]})
    want = _brute(pd.concat([df, probe], ignore_index=True)).iloc[-1]
    got = snap.loc[(1, 2)]
    assert got["inflow_1y"] == want["inflow_1y"] and got["backlog_2y"] == want["backlog_2y"]
    assert got["clearance_1y"] == pytest.approx(want["clearance_1y"])
