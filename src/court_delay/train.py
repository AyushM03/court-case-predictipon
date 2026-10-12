"""Fit the deployment model and the court lookup table for the API (D-017).

The evaluation model in notebooks 04/05 is trained on 2012–2015 filings only, so it can be tested
on later ones. Once the model is chosen, the API model is refit the same way on all 2012–2018
filings: it sees the most recent court conditions and drifts less (see 04_models, calibration).

    python -m court_delay.train                         # writes data/models/deploy/
    python -m court_delay.train --export backend/model  # copy the model for Vercel (D-019)
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from court_delay import config as C
from court_delay import models as M
from court_delay.features import court_snapshot

DEPLOY = C.DEPLOY
SNAPSHOT_DATE = "2019-01-01"        # the day after ADMIN_CENSOR_DATE: congestion a new filing faces
RECENT_FROM = 2016                  # filings used for court names, judge position and case mix
MIN_CATEGORY_CASES = 20             # a court "hears" a category with at least this many recent cases
SEED = 0


def court_names() -> pd.DataFrame:
    """Latest court name per (dist_code, court_no) in Maharashtra from the DDL court key."""
    key = pd.read_csv(C.RAW / "keys" / "cases_court_key.csv", dtype=str)
    key = key[key["state_code"].astype(int) == 1]
    key = key.assign(dist_code=key["dist_code"].astype(int), court_no=key["court_no"].astype(int),
                     year=key["year"].astype(int))
    key = key.sort_values("year").drop_duplicates(["dist_code", "court_no"], keep="last")
    return key[["dist_code", "court_no", "court_name"]]


def court_table() -> pd.DataFrame:
    """One row per active court: name, district, judge position, congestion as of SNAPSHOT_DATE,
    and the case categories it hears."""
    cols = ["year", "dist_code", "court_no", "district_name", "judge_position", "case_category",
            "filing_date", "duration_days", "event", "bad_dates"]
    df = pq.read_table(C.PROCESSED / "cases_maharashtra.parquet", columns=cols).to_pandas(
        strings_to_categorical=True)
    df = df[~df["bad_dates"]].reset_index(drop=True)
    snap = court_snapshot(df, SNAPSHOT_DATE)
    recent = df[df["year"] >= RECENT_FROM]
    keys = ["dist_code", "court_no"]
    info = recent.groupby(keys, observed=True).agg(
        district_name=("district_name", lambda s: s.mode().iat[0]),
        judge_position=("judge_position", lambda s: s.mode().iat[0]),
        recent_cases=("event", "size")).reset_index()
    mix = recent.groupby(keys + ["case_category"], observed=True).size().rename("n").reset_index()
    mix = mix[mix["n"] >= MIN_CATEGORY_CASES].sort_values("n", ascending=False)
    cats = mix.groupby(keys)["case_category"].agg(lambda s: [str(c) for c in s]).rename("categories")
    out = (info.merge(snap, on=keys).merge(court_names(), on=keys, how="left")
           .merge(cats.reset_index(), on=keys, how="left"))
    out = out[(out["inflow_1y"] > 0) & out["categories"].notna()]
    out["court_name"] = out["court_name"].fillna(out["judge_position"].astype(str))
    out["court_id"] = out["dist_code"].astype(str) + "-" + out["court_no"].astype(str)
    for c in ["district_name", "judge_position"]:
        out[c] = out[c].astype(str)
    return out.sort_values(["district_name", "court_name"]).reset_index(drop=True)


def fit_deploy_model():
    df = M.load()
    fit = df.sample(1_500_000, random_state=SEED + 1)
    val = df.drop(fit.index).sample(200_000, random_state=SEED + 2)
    meta = {
        "trained_on": "filings 2012-01-01..2018-12-31",
        "observation_ends": C.ADMIN_CENSOR_DATE,
        "snapshot_date": SNAPSHOT_DATE,
        "n_fit": len(fit), "n_valid": len(val),
        "clearance_fill": float(df["clearance_1y"].median()),
        "categories": {c: [str(v) for v in df[c].cat.categories] for c in M.CATEGORICAL},
        "built": date.today().isoformat(),
    }
    del df
    model = M.XGBCox(rounds=1500).fit(fit, val)
    meta["best_iteration"] = int(model.booster.best_iteration)
    meta["baseline_days"] = len(model.H0)
    return model, meta


def write_courts(courts: pd.DataFrame, path) -> None:
    """Court table as JSON (records): the API reads it without pyarrow."""
    rows = courts.astype(object).where(courts.notna(), None).to_dict(orient="records")
    for r in rows:
        r["categories"] = list(r["categories"])
    path.write_text(json.dumps(rows, ensure_ascii=False, default=_plain), encoding="utf-8")


def _plain(v):
    return v.item() if isinstance(v, np.generic) else str(v)


def export(dest) -> None:
    """Copy the deployment model to `dest` (backend/model for Vercel, D-019), with the booster in
    XGBoost's binary UBJSON format, which is about half the size of JSON and loads faster."""
    import shutil
    from court_delay.api import MODEL_FILES
    dest.mkdir(parents=True, exist_ok=True)
    for f in MODEL_FILES:
        shutil.copy2(DEPLOY / f, dest / f)
    booster = M.XGBCox.load(DEPLOY).booster          # keeps the best_iteration attribute
    booster.save_model(dest / "xgb_cox.ubj")
    (dest / "xgb_cox.json").unlink(missing_ok=True)
    print(f"exported {', '.join(MODEL_FILES)} and xgb_cox.ubj -> {dest}")


def main() -> None:
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--export":
        return export(Path(sys.argv[2]))
    DEPLOY.mkdir(parents=True, exist_ok=True)
    courts = court_table()
    write_courts(courts, DEPLOY / "courts.json")
    print(f"{len(courts)} active courts in {courts.district_name.nunique()} districts")
    model, meta = fit_deploy_model()
    model.save(DEPLOY)
    (DEPLOY / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"model: {meta['best_iteration'] + 1} trees, baseline to day {meta['baseline_days'] - 1}"
          f" -> {DEPLOY}")


if __name__ == "__main__":
    main()
