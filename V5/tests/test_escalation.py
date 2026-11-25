import json
from datetime import date
import app as A
from data_service import load_people

DF = load_people()
T = date(2026, 9, 11)


def convo(*qs):
    state, out = {}, []
    for q in qs:
        r, state = A.handle(q, state, DF, T)
        out.append(r)
    return out


def test_single_failure_not_escalated(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "LOG_PATH", tmp_path / "e.jsonl")
    r = convo("Who is the kindest person?")[0]
    assert r["status"] == "unsupported" and not r["escalated"]
    assert not (tmp_path / "e.jsonl").exists()


def test_two_failures_escalate_and_log(monkeypatch, tmp_path):
    log = tmp_path / "e.jsonl"
    monkeypatch.setattr(A, "LOG_PATH", log)
    r = convo("Who is the kindest person?", "blah blah")[1]
    assert r["escalated"] and "check people.xlsx" in r["answer"]
    rows = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["message"] == "blah blah"


def test_success_resets_streak(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "LOG_PATH", tmp_path / "e.jsonl")
    r = convo("Who is the kindest person?", "When is Rahul Patil's birthday?", "blah blah")
    assert not r[1]["escalated"] and not r[2]["escalated"]


def test_unknown_person_counts_as_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "LOG_PATH", tmp_path / "e.jsonl")
    r = convo("blah blah", "When is Zorblax's birthday?")[1]
    assert r["escalated"]


def test_long_message_is_cut_not_crashing():
    c = A.app.test_client()
    resp = c.post("/api/chat", json={"message": "birthdays in september " + "x" * 5000})
    assert resp.status_code == 200
    resp = c.post("/api/chat", json={"message": 12345})
    assert resp.status_code == 200