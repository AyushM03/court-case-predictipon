"""Helpers for survival modelling on the processed case table."""
import pandas as pd

from court_delay import config as C

from court_delay.labels import COURT_SYSTEM_PATTERN


def censor_at(df: pd.DataFrame, date=C.ADMIN_CENSOR_DATE) -> pd.DataFrame:
    """End observation at `date`: cases still open then (or decided later) become censored there.

    Needs `filing_date`, `duration_days`, `event`. Returns a copy with those two columns updated.
    """
    date = pd.Timestamp(date)
    out = df.copy()
    end = out["filing_date"] + pd.to_timedelta(out["duration_days"], unit="D")
    late = end > date
    out.loc[late, "duration_days"] = (date - out.loc[late, "filing_date"]).dt.days
    out.loc[late, "event"] = 0
    return out[out["duration_days"] >= 0]


def aggregate(df: pd.DataFrame, by: list[str] | str | None = None) -> pd.DataFrame:
    """Collapse to one row per (group, duration, event) with a count `n`.

    Durations are whole days, so 10M cases shrink to a few thousand rows per group, and
    lifelines fits on them with `weights=n` give the same estimates far faster.
    """
    by = [by] if isinstance(by, str) else list(by or [])
    keys = by + ["duration_days", "event"]
    return df.groupby(keys, observed=True).size().rename("n").reset_index()


def is_court_system(district_name: pd.Series) -> pd.Series:
    """True for Mumbai court systems and statewide tribunals in DDL's district key (D-009)."""
    return district_name.str.match(COURT_SYSTEM_PATTERN, na=False).astype(bool)
