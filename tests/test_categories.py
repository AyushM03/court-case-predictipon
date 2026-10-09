"""Case-type label -> case_category mapping, on real DDL label spellings."""
import pandas as pd
import pytest

from court_delay.categories import CIVIL, CRIMINAL, LABEL_RULES, add_case_category, categorize


@pytest.mark.parametrize("label, court, expected", [
    ("s.c.c.", "chief judicial magistrate", "summary_criminal"),
    ("ss casess  ss", "chief metropolitan magistrate", "summary_criminal"),
    ("s s", "criminal cases", "summary_criminal"),
    ("police cases ps", "metropolitan magistrate court", "summary_criminal"),
    ("r.c.c.", "judicial magistrate court", "regular_criminal"),
    ("police cases(w)", "metropolitan magistrate court", "regular_criminal"),
    ("summons warrent cases sw", "metropolitan magistrate court", "regular_criminal"),
    ("cri.bail appln.", "district and sessions court", "bail_remand"),
    ("a.b.a.", "city district and sessions court", "bail_remand"),
    ("cri.m.a.", "criminal cases", "criminal_misc"),
    ("cri.rev.app.", "district and sessions court", "criminal_appeal_revision"),
    ("sessions case", "district and sessions court", "sessions_special"),
    ("pocso spl case", "city civil and sessions court", "sessions_special"),
    ("pwdva appln.", "chief judicial magistrate", "domestic_violence"),
    ("r.c.s.", "civil judge junior division", "civil_suit"),
    ("spl.c.s.", "civil judge senior division", "civil_suit"),
    ("chamber summons", "civil court", "civil_misc"),
    ("r.c.a.", "district and sessions court", "civil_appeal_revision"),
    ("reg dkst", "district and sessions court", "execution"),
    ("m.a.c.p.", "district and sessions court", "motor_accident"),
    ("macp. dkst.", "district and sessions court", "motor_accident"),
    ("l.a.r.", "civil judge senior division", "land_acquisition"),
    ("marriage petn.", "civil judge senior division", "family"),
    ("complaint ulp", "industrial court", "labour"),
    ("succession", "civil judge senior division", "succession"),
])
def test_known_labels(label, court, expected):
    assert categorize(label, court) == expected


def test_specialised_court_overrides_ambiguous_label():
    assert categorize("petition a", "family court") == "family"
    assert categorize("appeal", "school tribunal") == "labour"
    assert categorize("money suit", "co-oprative court, solapur") == "arbitration_cooperative"


def test_unknown_and_missing():
    assert categorize("zzz", "civil court") == "other"
    assert categorize(None, None) == "other"


def test_every_rule_category_is_civil_or_criminal():
    cats = {cat for *_, cat in LABEL_RULES}
    assert cats <= CIVIL | CRIMINAL
    assert not CIVIL & CRIMINAL


def test_add_case_category_columns():
    df = pd.DataFrame({"type_label": ["s.c.c.", "r.c.s.", "zzz"],
                       "judge_position": ["jmfc", "civil court", "civil court"]})
    out = add_case_category(df)
    assert list(out["case_category"]) == ["summary_criminal", "civil_suit", "other"]
    assert out["is_criminal"].tolist()[:2] == [1, 0]
    assert pd.isna(out["is_criminal"].iloc[2])
