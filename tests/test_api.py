"""API endpoints on a tiny model and court table built in a temp folder."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from court_delay import models as M
from court_delay.api import create_app
from court_delay.train import write_courts

CATS = ["bail_remand", "civil_suit", "summary_criminal"]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    folder = tmp_path_factory.mktemp("deploy")
    rng = np.random.default_rng(0)
    n = 4000
    raw = pd.DataFrame({
        "district_name": rng.choice(["Pune", "Thane", "Mumbai CMM Courts"], n),
        "judge_position": rng.choice(["civil court", "jmfc"], n),
        "case_category": rng.choice(CATS, n),
        "inflow_1y": rng.integers(100, 5000, n).astype(float),
        "backlog_2y": rng.integers(100, 6000, n).astype(float),
        "clearance_1y": rng.uniform(0.2, 0.8, n),
    })
    raw["queue_ratio"] = raw["backlog_2y"] / raw["inflow_1y"]
    raw["is_criminal"] = (raw["case_category"] != "civil_suit").astype(float)
    speed = np.where(raw["case_category"] == "bail_remand", 30, 600) / raw["queue_ratio"].clip(0.3, 3)
    t = rng.exponential(speed).astype(int)
    c = rng.integers(0, 2500, n)
    raw["duration_days"], raw["event"] = np.minimum(t, c), (t <= c).astype(int)
    df = M.prepare(raw.copy())
    model = M.XGBCox(rounds=30).fit(df.iloc[:3500], df.iloc[3500:])
    model.save(folder)
    meta = {"snapshot_date": "2019-01-01", "trained_on": "test", "clearance_fill": 0.5,
            "categories": {k: [str(v) for v in df[k].cat.categories] for k in M.CATEGORICAL}}
    (folder / "meta.json").write_text(json.dumps(meta))
    courts = pd.DataFrame({
        "court_id": ["1-1", "1-2", "2-1"], "dist_code": [1, 1, 2], "court_no": [1, 2, 1],
        "court_name": ["Civil Court Pune", "JMFC Pune", "JMFC Thane"],
        "district_name": ["Pune", "Pune", "Thane"], "judge_position": ["civil court", "jmfc", "jmfc"],
        "recent_cases": [5000, 8000, 3000],
        "inflow_1y": [2000.0, 4000.0, 1500.0], "backlog_2y": [4000.0, 3000.0, 1500.0],
        "queue_ratio": [2.0, 0.75, 1.0], "clearance_1y": [0.3, 0.6, np.nan],
        "categories": [["civil_suit"], ["summary_criminal", "bail_remand"], ["summary_criminal", "bail_remand"]],
    })
    write_courts(courts, folder / "courts.json")
    return TestClient(create_app(folder))


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_meta_lists_courts_by_district(client):
    m = client.get("/api/meta").json()
    assert [d["district"] for d in m["districts"]] == ["Pune", "Thane"]
    assert {c["court_id"] for c in m["districts"][0]["courts"]} == {"1-1", "1-2"}
    assert {c["id"] for c in m["case_categories"]} >= set(CATS)
    assert next(c for c in m["case_categories"] if c["id"] == "bail_remand")["criminal"]


def test_predict_returns_a_valid_curve(client):
    r = client.post("/api/predict", json={"court_id": "1-2", "case_category": "bail_remand"})
    assert r.status_code == 200
    p = r.json()
    d = np.array([pt["decided"] for pt in p["curve"]])
    assert p["curve"][0]["day"] == 0 and (np.diff(d) >= -1e-9).all() and 0 <= d.min() and d.max() <= 1
    q = [x for x in p["quartile_days"] if x is not None]
    assert q == sorted(q) and p["median_days"] == p["quartile_days"][1]
    assert p["decided_by"]["1y"] <= p["decided_by"]["5y"]
    assert len(p["explanation"]) == len(M.NUMERIC + M.CATEGORICAL)
    assert p["comparison"]["courts_hearing_category"] == 2 and p["warnings"] == []
    assert p["court"]["district"] == "Pune" and p["congestion"]["queue_ratio"] == 0.75


def test_bail_is_faster_than_civil_suit(client):
    bail = client.post("/api/predict", json={"court_id": "1-2", "case_category": "bail_remand"}).json()
    suit = client.post("/api/predict", json={"court_id": "1-2", "case_category": "civil_suit"}).json()
    assert bail["decided_by"]["1y"] > suit["decided_by"]["1y"]


def test_rare_category_warns_and_missing_clearance_is_null(client):
    p = client.post("/api/predict", json={"court_id": "2-1", "case_category": "civil_suit"}).json()
    assert p["warnings"] and p["congestion"]["clearance_1y"] is None


def test_unknown_inputs(client):
    assert client.post("/api/predict", json={"court_id": "9-9", "case_category": "civil_suit"}).status_code == 404
    assert client.post("/api/predict", json={"court_id": "1-1", "case_category": "piracy"}).status_code == 422
    assert client.post("/api/predict", json={"court_id": "1-1"}).status_code == 422


def test_serves_spa_with_fallback(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    app = create_app(tmp_path, frontend=dist)          # model files are only loaded on /predict
    c = TestClient(app)
    assert c.get("/").text == "<div id=root></div>"
    assert c.get("/insights").text == "<div id=root></div>"          # client-side route
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/..%2F..%2Fpyproject.toml").text == "<div id=root></div>"  # no escaping the folder
    assert c.get("/api/nope").status_code == 404                     # API typos are not the SPA
