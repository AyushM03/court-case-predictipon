"""Raw DDL CSVs -> one state's survival table.

Usage:
    python -m court_delay.ingest --state Maharashtra --years 2010-2018
    python -m court_delay.ingest --state Maharashtra --years 2010 --skip-acts
"""
import argparse
from pathlib import Path

import pandas as pd

from court_delay import config as C


# ---------- helpers ----------

def find_file(folder: Path, stem: str) -> Path:
    """Locate `stem` as .csv or .csv.gz inside folder."""
    for suffix in ("", ".gz"):
        path = folder / f"{stem}{suffix}"
        if path.exists():
            return path
    raise FileNotFoundError(f"{stem}[.gz] not found in {folder} (see docs/DATA.md)")


def check_columns(path: Path, expected: list[str]) -> None:
    actual = pd.read_csv(path, nrows=0).columns.tolist()
    missing = [c for c in expected if c not in actual]
    if missing:
        raise KeyError(
            f"{path.name} is missing {missing}.\nActual columns: {actual}\n"
            "Update src/court_delay/config.py to match."
        )


def read_key(filename: str, keys_dir: Path) -> pd.DataFrame:
    return pd.read_csv(find_file(keys_dir, filename.removesuffix(".gz")))


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of {candidates} in key columns {df.columns.tolist()}")


def slug(state: str) -> str:
    return state.strip().lower().replace(" ", "_")


def parse_years(spec: str) -> list[int]:
    if "-" in spec:
        start, end = spec.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(y) for y in spec.split(",")]


# ---------- step 1: state code ----------

def resolve_state_code(state: str, keys_dir: Path) -> int:
    key = read_key(C.STATE_KEY[0], keys_dir)
    name_col = C.STATE_KEY[1]
    code_col = pick_col(key, ["state_code", "state"])
    match = key[key[name_col].str.strip().str.lower() == state.strip().lower()]
    codes = match[code_col].unique()
    if len(codes) != 1:
        raise ValueError(
            f"Expected exactly one code for {state!r}, got {codes}. "
            f"Available: {sorted(key[name_col].dropna().unique())}"
        )
    return int(codes[0])


# ---------- step 2: filter raw cases per year ----------

def filter_cases_year(year: int, state_code: int, state: str,
                      raw_dir: Path = C.RAW, out_dir: Path = C.INTERIM) -> Path:
    out = out_dir / f"cases_{slug(state)}_{year}.parquet"
    if out.exists():
        print(f"  {year}: already done -> {out.name}")
        return out
    path = find_file(raw_dir / "cases", f"cases_{year}.csv")
    check_columns(path, C.CASE_COLS)

    parts, total = [], 0
    reader = pd.read_csv(path, usecols=C.CASE_COLS, chunksize=C.CHUNK_ROWS,
                         dtype={"ddl_case_id": str, "judge_position": str})
    for chunk in reader:
        total += len(chunk)
        parts.append(chunk[chunk["state_code"] == state_code])
    df = pd.concat(parts, ignore_index=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"  {year}: kept {len(df):,} of {total:,} rows -> {out.name}")
    return out


# ---------- step 3: filter acts/sections to this state's cases ----------

def filter_acts(case_ids: set[str], state: str,
                raw_dir: Path = C.RAW, out_dir: Path = C.INTERIM) -> Path | None:
    out = out_dir / f"acts_{slug(state)}.parquet"
    try:
        path = find_file(raw_dir, C.ACTS_FILE)
    except FileNotFoundError:
        print("  acts_sections not found, skipping (download later)")
        return None
    check_columns(path, C.ACT_COLS)
    parts = []
    for chunk in pd.read_csv(path, usecols=C.ACT_COLS, chunksize=C.CHUNK_ROWS,
                             dtype={"ddl_case_id": str}):
        parts.append(chunk[chunk["ddl_case_id"].isin(case_ids)])
    df = pd.concat(parts, ignore_index=True)
    df.to_parquet(out, index=False)
    print(f"  acts: {len(df):,} rows -> {out.name}")
    return out


# ---------- step 4: join keys, compute duration + censoring ----------

def join_label(df: pd.DataFrame, key: pd.DataFrame, code_col: str,
               label_col: str, new_name: str, extra_on: list[str] = ()) -> pd.DataFrame:
    """Left-join a lookup, joining on `year` too when the key has it."""
    on = [c for c in ["year", *extra_on] if c in key.columns] + [code_col]
    key = key[on + [label_col]].drop_duplicates(on).rename(columns={label_col: new_name})
    merged = df.merge(key, on=on, how="left", validate="many_to_one")
    unmatched = merged[new_name].isna() & merged[code_col].notna()
    if unmatched.any():
        print(f"  warning: {unmatched.sum():,} rows have {code_col} codes with no label")
    return merged


def add_survival_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    for col in C.DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    # Cutoff = latest date that has actually happened in the data (next_list is a future date).
    cutoff = df[["date_of_decision", "date_last_list", "date_first_list"]].max().max()

    df["filing_date"] = df["date_of_filing"]
    df["decision_date"] = df["date_of_decision"].where(df["date_of_decision"] <= cutoff)
    df["event"] = df["decision_date"].notna().astype("int8")
    end = df["decision_date"].fillna(cutoff)
    df["duration_days"] = (end - df["filing_date"]).dt.days
    df["bad_dates"] = (
        df["filing_date"].isna()
        | (df["filing_date"] < pd.Timestamp(C.MIN_VALID_DATE))
        | (df["filing_date"] > cutoff)
        | (df["duration_days"] < 0)
    )
    return df, cutoff


def build_survival_table(state: str, years: list[int], keys_dir: Path = C.RAW / "keys",
                         interim_dir: Path = C.INTERIM, out_dir: Path = C.PROCESSED) -> Path:
    df = pd.concat(
        [pd.read_parquet(interim_dir / f"cases_{slug(state)}_{y}.parquet") for y in years],
        ignore_index=True,
    )
    df["state_name"] = state

    dist = read_key(C.DISTRICT_KEY[0], keys_dir)
    dist = dist.rename(columns={pick_col(dist, ["state_code", "state"]): "state_code",
                                pick_col(dist, ["dist_code", "district"]): "dist_code"})
    df = join_label(df, dist, "dist_code", C.DISTRICT_KEY[1], "district_name", ["state_code"])
    df = join_label(df, read_key(C.TYPE_KEY[0], keys_dir), "type_name", C.TYPE_KEY[1], "type_label")
    df = join_label(df, read_key(C.DISP_KEY[0], keys_dir), "disp_name", C.DISP_KEY[1], "disp_label")

    df, cutoff = add_survival_columns(df)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"cases_{slug(state)}.parquet"
    df.to_parquet(out, index=False)

    good = df[~df["bad_dates"]]
    print(f"\nSurvival table -> {out}")
    print(f"  rows: {len(df):,}   bad dates: {df['bad_dates'].sum():,}")
    print(f"  censoring cutoff: {cutoff.date()}")
    print(f"  decided: {good['event'].mean():.1%}   pending (censored): {1 - good['event'].mean():.1%}")
    print(f"  median duration, decided only (biased low!): "
          f"{good.loc[good['event'] == 1, 'duration_days'].median():.0f} days")
    return out


# ---------- CLI ----------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="Maharashtra")
    ap.add_argument("--years", default="2010-2018", help="e.g. 2010-2018 or 2010,2011")
    ap.add_argument("--skip-acts", action="store_true")
    args = ap.parse_args()

    years = parse_years(args.years)
    code = resolve_state_code(args.state, C.RAW / "keys")
    print(f"{args.state} -> state_code {code}")

    print("Filtering cases:")
    for year in years:
        filter_cases_year(year, code, args.state)

    out = build_survival_table(args.state, years)

    if not args.skip_acts:
        ids = set(pd.read_parquet(out, columns=["ddl_case_id"])["ddl_case_id"])
        filter_acts(ids, args.state)


if __name__ == "__main__":
    main()
