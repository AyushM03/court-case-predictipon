"""End-to-end ingest on a tiny synthetic copy of the DDL layout."""
import pandas as pd
import pytest

from court_delay import config as C
from court_delay import ingest


@pytest.fixture
def raw(tmp_path):
    keys = tmp_path / "raw" / "keys"
    cases = tmp_path / "raw" / "cases"
    keys.mkdir(parents=True)
    cases.mkdir(parents=True)

    pd.DataFrame({"year": [2010, 2010], "state_code": [1, 2],
                  "state_name": ["Maharashtra", "Goa"]}).to_csv(keys / "cases_state_key.csv", index=False)
    pd.DataFrame({"year": [2010, 2010, 2010], "state_code": [1, 1, 2], "dist_code": [1, 2, 1],
                  "district_name": ["Pune", "Nagpur", "North Goa"]}).to_csv(keys / "cases_district_key.csv", index=False)
    pd.DataFrame({"year": [2010, 2010], "type_name": [10, 20],
                  "type_name_s": ["civil suit", "criminal"]}).to_csv(keys / "type_name_key.csv", index=False)
    pd.DataFrame({"year": [2010], "disp_name": [5],
                  "disp_name_s": ["decided"]}).to_csv(keys / "disp_name_key.csv", index=False)

    rows = [
        # id, state, dist, type, disp, filing,       decision,     last_list
        ("a", 1, 1, 10, 5,    "2010-01-01", "2010-12-31", "2010-12-31"),   # decided, 364 days
        ("b", 1, 2, 20, None, "2010-06-01", None,         "2018-12-31"),   # pending -> censored
        ("c", 1, 1, 10, 5,    "2010-05-01", "2009-01-01", "2010-05-01"),   # decision before filing
        ("d", 2, 1, 10, 5,    "2010-01-01", "2011-01-01", "2011-01-01"),   # other state, dropped
    ]
    df = pd.DataFrame(rows, columns=["ddl_case_id", "state_code", "dist_code", "type_name", "disp_name",
                                     "date_of_filing", "date_of_decision", "date_last_list"])
    df["year"] = 2010
    for col in C.CASE_COLS:
        if col not in df:
            df[col] = None
    df["date_first_list"] = df["date_of_filing"]
    df.to_csv(cases / "cases_2010.csv", index=False)
    return tmp_path


def test_pipeline(raw, monkeypatch):
    monkeypatch.setattr(C, "CUTOFF_QUANTILE", 1.0)  # too few rows for a quantile to mean much
    code = ingest.resolve_state_code("maharashtra", raw / "raw" / "keys")
    assert code == 1

    ingest.filter_cases_year(2010, code, "Maharashtra", raw / "raw", raw / "interim")
    out = ingest.build_survival_table("Maharashtra", [2010], raw / "raw" / "keys",
                                      raw / "interim", raw / "processed")
    df = pd.read_parquet(out).set_index("ddl_case_id")

    assert set(df.index) == {"a", "b", "c"}
    assert df.loc["a", "district_name"] == "Pune"
    assert df.loc["b", "type_label"] == "criminal"
    assert df.loc["a", "case_category"] == "civil_suit" and df.loc["a", "is_criminal"] == 0

    assert df.loc["a", "event"] == 1 and df.loc["a", "duration_days"] == 364
    # pending case is censored at the latest observed date, not dropped
    assert df.loc["b", "event"] == 0
    assert df.loc["b", "duration_days"] == (pd.Timestamp("2018-12-31") - pd.Timestamp("2010-06-01")).days
    assert df.loc["c", "bad_dates"] and not df.loc["a", "bad_dates"]


def test_cutoff_ignores_typo_dates():
    n = 10_000
    df = pd.DataFrame({c: [None] * n for c in C.DATE_COLS})
    df["date_of_filing"] = "2010-01-01"
    df["date_of_decision"] = "2015-01-01"
    df["date_last_list"] = "2019-06-30"
    df.loc[0, "date_last_list"] = "2099-01-01"  # one typo
    _, cutoff = ingest.add_survival_columns(df)
    assert cutoff == pd.Timestamp("2019-06-30")


def test_missing_column_message(tmp_path):
    p = tmp_path / "x.csv"
    pd.DataFrame({"foo": [1]}).to_csv(p, index=False)
    with pytest.raises(KeyError, match="Actual columns"):
        ingest.check_columns(p, ["ddl_case_id"])


def test_parse_years():
    assert ingest.parse_years("2010-2012") == [2010, 2011, 2012]
    assert ingest.parse_years("2010,2015") == [2010, 2015]


def test_district_key_is_cumulative_not_per_year():
    # DDL's district key lists each district once, under the year it first appeared.
    key = pd.DataFrame({"year": [2010, 2010, 2017], "state_code": [1, 22, 22], "dist_code": [1, 18, 18],
                        "district_name": ["Pune", "Hoshiarpurr", "Hoshiarpur"]})
    cases = pd.DataFrame({"year": [2010, 2015, 2012], "state_code": [1, 1, 22], "dist_code": [1, 1, 18]})
    out = ingest.join_label(cases, key, "dist_code", "district_name", "district_name",
                            ["state_code"], by_year=False)
    assert out["district_name"].tolist() == ["Pune", "Pune", "Hoshiarpur"]
