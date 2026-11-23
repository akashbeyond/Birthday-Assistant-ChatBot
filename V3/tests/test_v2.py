import json
from datetime import date
from data_service import load_people
from nlu import parse
from service import execute

DF = load_people()
TODAY = date(2026, 9, 11)


def run(q):
    p = parse(q, DF)
    json.dumps(p)  # parsed output must be JSON-serialisable (needed for V4)
    return p, execute(p, DF, TODAY)


def test_names_cleaned():
    assert not DF["Name"].str.contains(r"\d").any()


def test_intents():
    assert run("What are the upcoming birthdays?")[0]["intent"] == "upcoming_birthdays"
    assert run("How many birthdays are there next month?")[0]["intent"] == "count_birthdays"
    assert run("Where does Rahul Patil stay?")[0]["intent"] == "person_place"
    assert run("How old is Rahul Patil?")[0]["intent"] == "person_age"
    assert run("Who stays in Bengaluru?")[0]["intent"] == "place_search"
    assert run("Tell me something poetic")[0]["intent"] == "unknown"


def test_entities():
    e = run("Any nephews with birthdays in September?")[0]["entities"]
    assert e["relationship"] == "Nephew" and e["month"] == 9


def test_named_person():
    assert "18 September 2004" in run("When is Rahul Patil's birthday?")[1]["answer"]


def test_my_wife():
    a = run("When is my wife's birthday?")[1]["answer"]
    assert "Lakshmi Rao" in a and "Pallavi" not in a


def test_nephew_september():
    a = run("Any nephew birthdays in September?")[1]["answer"]
    assert "Rahul Patil" in a and "Nikhil Hegde" not in a


def test_count_next_month():
    assert "birthdays in October" in run("How many birthdays are there next month?")[1]["answer"]


def test_ambiguous_name():
    r = run("When is Nikhil's birthday?")[1]
    assert r["status"] == "ambiguous" and len(r["result_ids"]) >= 4


def test_invalid_date():
    assert run("Any birthdays on 31 February?")[1]["status"] == "invalid"


def test_specific_day():
    assert "Rahul Patil" in run("birthdays on 18 September")[1]["answer"]


def test_windows():
    assert "Rahul Patil" in run("Who has birthdays within 10 days?")[1]["answer"]
    assert run("birthday day after tomorrow")[0]["entities"]["relative_date"] == "day_after_tomorrow"


def test_unsupported():
    assert run("Who is the kindest person?")[1]["status"] == "unsupported"
