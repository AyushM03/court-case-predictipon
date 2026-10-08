"""Raw DDL CSVs -> one state's survival table.

Usage:
    python -m court_delay.ingest --state Maharashtra --years 2010-2018
    python -m court_delay.ingest --state Maharashtra --years 2010 --skip-acts
"""
import argparse
import csv
import gzip
import io
import re
import tarfile
from contextlib import contextmanager
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


class _RawReader(io.RawIOBase):
    """Adapts a streaming tar member (no seekable()) so io.TextIOWrapper accepts it."""
    def __init__(self, src):
        self.src = src

    def readable(self):
        return True

    def readinto(self, b):
        data = self.src.read(len(b))
        b[:len(data)] = data
        return len(data)


@contextmanager
def open_cases_year(year: int, cases_dir: Path):
    """Yield (name, text stream) for cases_<year>: a loose CSV if present, else streamed straight
    out of cases.tar.gz (DDL ships all years in one archive; extracting them needs too much disk)."""
    try:
        path = find_file(cases_dir, f"cases_{year}.csv")
    except FileNotFoundError:
        path = None
    if path is not None:
        with open(path, "rb") as raw:
            binary = gzip.open(raw) if path.suffix == ".gz" else raw
            yield path.name, io.TextIOWrapper(binary, encoding="utf-8", newline="")
        return
    archive = cases_dir / "cases.tar.gz"
    if not archive.exists():
        raise FileNotFoundError(f"cases_{year}.csv[.gz] or {archive.name} not in {cases_dir} "
                                "(run: python -m court_delay.fetch download cases)")
    pattern = re.compile(rf"(^|/)cases_{year}\.csv$")
    with tarfile.open(archive, "r|gz") as tar:
        for member in tar:
            if member.isfile() and pattern.search(member.name):
                print(f"  {year}: streaming {member.name} from {archive.name}")
                binary = io.BufferedReader(_RawReader(tar.extractfile(member)), 1 << 20)
                yield member.name, io.TextIOWrapper(binary, encoding="utf-8", newline="")
                return
    raise FileNotFoundError(f"cases_{year}.csv not found inside {archive}")


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
    with open_cases_year(year, raw_dir / "cases") as (name, f):
        header = next(csv.reader([f.readline()]))
        missing = [c for c in C.CASE_COLS if c not in header]
        if missing:
            raise KeyError(f"{name} is missing {missing}.\nActual columns: {header}\n"
                           "Update src/court_delay/config.py to match.")
        parts, total = [], 0
        reader = pd.read_csv(f, names=header, header=None, usecols=C.CASE_COLS,
                             chunksize=C.CHUNK_ROWS,
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
               label_col: str, new_name: str, extra_on: list[str] = (),
               by_year: bool = True) -> pd.DataFrame:
    """Left-join a lookup, joining on `year` too when the key has it and `by_year` is set.

    With by_year=False the key is treated as one cumulative list (DDL's district key lists each
    district once, under the year it first appeared); the latest spelling of a code wins.
    """
    if not by_year and "year" in key.columns:
        key = key.sort_values("year").drop_duplicates([*extra_on, code_col], keep="last")
    on = [c for c in ["year", *extra_on] if c in key.columns and (by_year or c != "year")] + [code_col]
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
    # Use a high quantile, not the max: a few typo dates (e.g. 2022 first hearings in data
    # collected ~2019-20) would otherwise push the cutoff years too late.
    observed = pd.concat([df["date_of_decision"], df["date_last_list"]]).dropna()
    cutoff = observed.quantile(C.CUTOFF_QUANTILE).normalize()

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
    df = join_label(df, dist, "dist_code", C.DISTRICT_KEY[1], "district_name", ["state_code"],
                    by_year=False)
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
