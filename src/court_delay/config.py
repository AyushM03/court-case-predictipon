"""Paths and expected raw-data schema. Edit names here if the real DDL files differ."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"

CHUNK_ROWS = 1_000_000

# Columns read from cases_YYYY.csv (everything else is skipped to save memory).
CASE_COLS = [
    "ddl_case_id", "year", "state_code", "dist_code", "court_no", "judge_position",
    "female_defendant", "female_petitioner", "female_adv_def", "female_adv_pet",
    "type_name", "purpose_name", "disp_name",
    "date_of_filing", "date_of_decision", "date_first_list", "date_last_list", "date_next_list",
]
DATE_COLS = ["date_of_filing", "date_of_decision", "date_first_list", "date_last_list", "date_next_list"]

# Lookup files in data/raw/keys and the name column that holds the human label.
STATE_KEY = ("cases_state_key.csv", "state_name")
DISTRICT_KEY = ("cases_district_key.csv", "district_name")
TYPE_KEY = ("type_name_key.csv", "type_name_s")
DISP_KEY = ("disp_name_key.csv", "disp_name_s")

ACTS_FILE = "acts_sections.csv"
ACT_COLS = ["ddl_case_id", "act", "section", "criminal"]

# Dates outside [MIN_VALID_DATE, cutoff] are treated as data errors.
MIN_VALID_DATE = "2000-01-01"

# Censoring cutoff = this quantile of observed decision / last-hearing dates (robust to typo dates).
CUTOFF_QUANTILE = 0.999
