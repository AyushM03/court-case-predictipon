"""Court congestion features at the filing date, and the Week 4 modelling table.

For a case filed on day t in court c (court = dist_code + court_no):
- inflow_1y     cases filed in c during [t-365, t)
- backlog_2y    cases filed in c during [t-730, t) and still undecided at t (not decided before t)
- clearance_1y  share of cases filed in c during [t-730, t-365) that were decided before t
- queue_ratio   backlog_2y / inflow_1y: roughly how many years of new work are already waiting

Each window looks back a fixed span, so the features are complete for filings from
FEATURE_START on (the data starts in 2010 and has no pre-2010 backlog). They only use what was
known on day t: whether a case had been decided before t, never its future.

    python -m court_delay.features        # writes data/processed/model_maharashtra.parquet
"""
import numba
import numpy as np
import pandas as pd

from court_delay import config as C
from court_delay.survival import censor_at

BACKLOG_DAYS = 730
INFLOW_DAYS = 365
FEATURE_START = "2012-01-01"   # first filing date with full look-back windows
MODEL_FILE = "model_maharashtra.parquet"


@numba.njit(cache=True)
def _court_features(f, e, backlog_days, inflow_days):
    """f, e: filing and end day numbers for one court, sorted by f. End = decision day, or a day
    after every filing for undecided cases. Returns (inflow, backlog, cleared, cohort) per case."""
    n = len(f)
    order_e = np.argsort(e, kind="mergesort")
    tree = np.zeros(n + 1, np.int64)               # Fenwick tree over positions in f-order
    inflow = np.empty(n, np.int64)
    backlog = np.empty(n, np.int64)
    cleared = np.empty(n, np.int64)
    cohort = np.empty(n, np.int64)
    p = 0
    for i in range(n):
        t = f[i]
        while p < n and e[order_e[p]] < t:         # cases decided before t
            k = order_e[p] + 1
            while k <= n:
                tree[k] += 1
                k += k & -k
            p += 1
        hi = np.searchsorted(f, t)                 # first case filed on day t
        lo_b = np.searchsorted(f, t - backlog_days)
        lo_i = np.searchsorted(f, t - inflow_days)
        inflow[i] = hi - lo_i
        dec_b = _prefix(tree, hi) - _prefix(tree, lo_b)
        backlog[i] = (hi - lo_b) - dec_b
        cohort[i] = lo_i - lo_b                    # filed in [t-730, t-365)
        cleared[i] = _prefix(tree, lo_i) - _prefix(tree, lo_b)
    return inflow, backlog, cleared, cohort


@numba.njit(cache=True)
def _prefix(tree, k):
    s = 0
    while k > 0:
        s += tree[k]
        k -= k & -k
    return s


def add_congestion(df: pd.DataFrame) -> pd.DataFrame:
    """Add inflow_1y, backlog_2y, queue_ratio, clearance_1y. Needs dist_code, court_no, filing_date,
    duration_days, event (the processed table, before any administrative censoring)."""
    day0 = pd.Timestamp("2000-01-01")
    f = (df["filing_date"] - day0).dt.days.to_numpy(np.int64)
    e = f + df["duration_days"].to_numpy(np.int64)
    e = np.where(df["event"].to_numpy() == 1, e, np.iinfo(np.int64).max)   # undecided: never "before t"
    court = df.groupby(["dist_code", "court_no"], sort=False).ngroup().to_numpy()
    order = np.lexsort((f, court))
    bounds = np.flatnonzero(np.diff(court[order])) + 1
    out = {k: np.empty(len(df), np.float64) for k in ("inflow_1y", "backlog_2y", "cleared", "cohort")}
    for idx in np.split(order, bounds):
        res = _court_features(f[idx], e[idx], BACKLOG_DAYS, INFLOW_DAYS)
        for k, v in zip(out, res):
            out[k][idx] = v
    df = df.copy()
    df["inflow_1y"] = out["inflow_1y"]
    df["backlog_2y"] = out["backlog_2y"]
    df["queue_ratio"] = out["backlog_2y"] / np.maximum(out["inflow_1y"], 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        df["clearance_1y"] = np.where(out["cohort"] > 0, out["cleared"] / out["cohort"], np.nan)
    return df


MODEL_COLS = ["ddl_case_id", "year", "filing_date", "dist_code", "court_no", "district_name",
              "judge_position", "case_category", "is_criminal", "duration_days", "event"]


def build_model_table(path=C.PROCESSED / "cases_maharashtra.parquet") -> pd.DataFrame:
    df = pd.read_parquet(path, columns=MODEL_COLS + ["bad_dates"])
    df = df[~df["bad_dates"]].drop(columns="bad_dates").reset_index(drop=True)
    df = add_congestion(df)
    df = df[df["filing_date"] >= FEATURE_START]
    return censor_at(df, C.ADMIN_CENSOR_DATE).reset_index(drop=True)


def main() -> None:
    df = build_model_table()
    out = C.PROCESSED / MODEL_FILE
    df.to_parquet(out, index=False)
    print(f"{len(df):,} cases filed {df.filing_date.min().date()}..{df.filing_date.max().date()} -> {out}")
    print(df[["inflow_1y", "backlog_2y", "queue_ratio", "clearance_1y"]].describe().round(2).to_string())


if __name__ == "__main__":
    main()
