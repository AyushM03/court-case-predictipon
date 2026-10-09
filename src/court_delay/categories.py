"""Map DDL's messy case-type labels (1,160 in Maharashtra) to a small `case_category`.

Labels are free text typed by each court ("ss cases", "ss casess", "s s" are the same type), so
rules run on a normalised form. Specialised courts (family, labour, co-operative, MACT) are
recognised by `judge_position` first, because their labels ("petition a", "appeal") are ambiguous.

    python -m court_delay.categories            # add case_category + is_criminal to the parquet
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from court_delay import config as C

CRIMINAL = {
    "summary_criminal", "regular_criminal", "sessions_special", "bail_remand",
    "criminal_misc", "criminal_appeal_revision", "domestic_violence", "juvenile",
}
CIVIL = {
    "civil_suit", "civil_appeal_revision", "civil_misc", "execution", "motor_accident",
    "land_acquisition", "arbitration_cooperative", "family", "labour", "succession",
}

# judge_position (normalised) -> category, checked before the label.
COURT_RULES: list[tuple[str, str]] = [
    (r"\bfamily court\b", "family"),
    (r"\b(labour|industrial|inustrial) court\b|\bschool tribunal\b", "labour"),
    (r"\bco ?op[a-z]*\b", "arbitration_cooperative"),
    (r"\bmotor accidents? claims tribunal\b", "motor_accident"),
    (r"\bjuvenile\b", "juvenile"),
]

# Label rules, first match wins. `t` = label with all non-letters removed ("s.c.c." -> "scc"),
# `n` = label with punctuation turned into single spaces ("cri.bail appln." -> "cri bail appln").
LABEL_RULES: list[tuple[str, str, str]] = [
    # family / domestic violence before generic "petition" and "appln"
    ("n", r"\b(pwdva|dvc?|domestic violence)\b|^d v\b", "domestic_violence"),
    ("n", r"\bmarriage\b|\bdivorce\b|\bmatrimonial\b|\bhma\b|^petition (no )?[a-z]{1,2}$", "family"),
    ("n", r"\bjuvenile\b|^jw$|\bjjb\b", "juvenile"),
    # motor accident claims (incl. their execution and misc applications)
    ("n", r"\bm ?a ?c ?p\b|\bmact\b|\bmotor\b", "motor_accident"),
    # labour
    ("n", r"\bulp\d*\b|\bida\b|\bpga\b|\bwca\b|\bw c f a\b|\bindustrial\b", "labour"),
    # criminal
    ("n", r"\bbail\b|^a ?b ?a$|\bremand\b|\b(m ?a in )?aba\b|^(pmla )?ba$", "bail_remand"),
    ("n", r"\b(cri|criminal)\b.*\b(appeal|app|rev|revn|revision)\b|\bcri\.? ?municipal\b|\bmunci\b", "criminal_appeal_revision"),
    ("n", r"\bsessions? case\b|\bspl\b.*\bcase\b|\bpocso\b|\bndps\b.*\bcase\b|\batro\b|\bacb\b|\bcbi\b|\bmpid\b|\bsecu\b|\bmcoc|\bmocca\b|\bpmla\b|\btada\b|\bp ?i ?d\b", "sessions_special"),
    # magistrate cases: SCC / "summons" (ss, s, ps) vs RCC / "warrant" (w, pw, sw). Metropolitan
    # courts write these as "<police|private|summons|ss> cases <code>" in many spellings.
    ("n", r"^(chamber summons|summons for judgt)", "civil_misc"),
    ("n", r"^(r c c|rcc|cri(minal)? case|p?w|p w|sw|s w|sw cases|ta)$", "regular_criminal"),
    ("n", r"^misc(ellaneous)?( cases?)?( misc)?$", "criminal_misc"),
    ("n", r"^(s c c|scc|p s|ps|ss|s s|s)$", "summary_criminal"),
    ("n", r"^(ss|s s|summons|police|private|notice)\b.*\b(p?w|sw|h|warr[ae]nt)$|^(police|private) warr", "regular_criminal"),
    ("n", r"^(ss|s s|summons|police|private|notice)\b", "summary_criminal"),
    ("n", r"\b(cri|criminal)\b|\bndps\b|\bmisc appln\b|\bm a in sessions\b|\bchild prot\b", "criminal_misc"),
    # civil
    ("n", r"\bl ?a ?r\b|\bland acq", "land_acquisition"),
    ("n", r"\barbitration\b|^c ?c ?a?$|\bco ?op", "arbitration_cooperative"),
    ("n", r"\bsuccession\b|\bprobate\b|\bheirship\b", "succession"),
    ("n", r"\bd ?k ?s?t\b|\bdarkhast\b|\bexecution\b|\bexe\b|\bfinal decree\b", "execution"),
    ("t", r"^(rca|mca|civilrevn|revision|misc ?appeal|appeal\w{0,2}|civilappeal|rcappeal)$", "civil_appeal_revision"),
    ("n", r"\b(civil )?(appeal|revn|revision)\b", "civil_appeal_revision"),
    ("t", r"^(rcs|splcs|suit|civilsuit|moneysuit|sumcivsuit|summarycivilsuit|regsumsuit|splsumsuit|summary|rae|raer|rad|marji|ra[ed]?r?)$", "civil_suit"),
    ("n", r"\bsuit\b|\bc ?s\b", "civil_suit"),
    ("n", r"\bcivil\b|\bnotice of motion\b|\bchamber summons\b|\bc appln\b|\bm ?j\b|\bmisc\b|\belec|\bpetition\b|\bm a n r j i\b|\bsummons for judgt\b", "civil_misc"),
]

_COURT = [(re.compile(p), cat) for p, cat in COURT_RULES]
_LABEL = [(form, re.compile(p), cat) for form, p, cat in LABEL_RULES]


def _norm(s) -> str:
    if not isinstance(s, str):  # None / NaN
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower())).strip()


def categorize(label: str | None, judge_position: str | None = None) -> str:
    """Category for one (type label, judge position) pair; "other" when nothing matches."""
    court = _norm(judge_position)
    for rx, cat in _COURT:
        if rx.search(court):
            return cat
    n = _norm(label)
    t = re.sub(r"[^a-z]", "", n)
    for form, rx, cat in _LABEL:
        if rx.search(t if form == "t" else n):
            return cat
    return "other"


def add_case_category(df: pd.DataFrame) -> pd.DataFrame:
    """Add `case_category` and `is_criminal` (1/0, NA for "other"). Maps unique pairs only."""
    pairs = df[["type_label", "judge_position"]].drop_duplicates()
    pairs["case_category"] = [categorize(l, j) for l, j in pairs.itertuples(index=False)]
    df = df.merge(pairs, on=["type_label", "judge_position"], how="left")
    crim = df["case_category"].map(lambda c: 1 if c in CRIMINAL else 0 if c in CIVIL else pd.NA)
    df["is_criminal"] = crim.astype("Int8")
    df["case_category"] = df["case_category"].astype("category")
    return df


def update_parquet(path: Path) -> None:
    """Add the category columns to an existing processed table, one row group at a time."""
    src = pq.ParquetFile(path)
    tmp = path.with_suffix(".tmp.parquet")
    writer = None
    try:
        for batch in src.iter_batches(batch_size=C.CHUNK_ROWS):
            df = batch.to_pandas().drop(columns=["case_category", "is_criminal"], errors="ignore")
            df = add_case_category(df)
            df["case_category"] = df["case_category"].astype(str)
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(tmp, table.schema)
            writer.write_table(table.cast(writer.schema))
    finally:
        if writer is not None:
            writer.close()
        src.close()  # Windows won't replace a file that is still open
    tmp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="Maharashtra")
    args = ap.parse_args()
    path = C.PROCESSED / f"cases_{args.state.lower().replace(' ', '_')}.parquet"
    update_parquet(path)
    df = pd.read_parquet(path, columns=["case_category", "is_criminal"])
    print(f"{path}: {len(df):,} rows")
    print((df["case_category"].value_counts(normalize=True) * 100).round(2).to_string())
    print(f"criminal share: {df['is_criminal'].mean():.1%}")


if __name__ == "__main__":
    main()
