from datetime import date
import app as A
from data_service import load_people

DF = load_people()
TODAY = date(2026, 9, 11)


def convo(*qs):
    state, out = {}, []
    for q in qs:
        r, state = A.handle(q, state, DF, TODAY)
        out.append(r)
    return out


def test_followup_month():
    r = convo("Any nephew birthdays in September?", "What about October?")[1]
    assert "Nikhil Hegde" in r["answer"] and "Rahul Patil" not in r["answer"]
    assert r["parsed"]["entities"]["relationship"] == "Nephew"
    assert r["parsed"]["entities"]["month"] == 10


def test_followup_relationship():
    r = convo("Birthdays in September", "What about nieces?")[1]
    assert r["parsed"]["entities"]["month"] == 9 and "Ananya Patil" in r["answer"]


def test_clarify_then_narrow():
    a, b, c = convo("When is my nephew's birthday?", "Nikhil", "Nikhil Hegde")
    assert a["status"] == "ambiguous"
    assert b["status"] == "ambiguous" and "Nikhil Hegde" in b["answer"] and "Nikhil Bhat" in b["answer"]
    assert "03 October 2001" in c["answer"]


def test_clarify_unique_name():
    a, b = convo("When is my nephew's birthday?", "Rahul")
    assert "18 September 2004" in b["answer"]


def test_reset_clears_context():
    r, _ = A.handle("What about October?", {}, DF, TODAY)
    assert r["status"] == "unsupported" or "relationship" not in r["parsed"]["entities"]


def test_new_topic_not_polluted():
    r = convo("Any nephew birthdays in September?", "When is Rahul Patil's birthday?")[1]
    assert "Rahul Patil's birthday is 18 September 2004" in r["answer"]


def test_plural_still_lists():
    assert convo("Any nephews birthdays in September?")[0]["status"] == "ok"


def test_flask_session_roundtrip():
    c = A.app.test_client()
    c.post("/api/chat", json={"message": "Any nephew birthdays in September?"})
    r = c.post("/api/chat", json={"message": "What about October?"}).get_json()
    assert r["parsed"]["entities"]["relationship"] == "Nephew"
    c.post("/api/reset")
    r = c.post("/api/chat", json={"message": "What about October?"}).get_json()
    assert "relationship" not in r["parsed"]["entities"]


def test_fresh_question_not_a_followup():
    r = convo("Any nephew birthdays in September?", "Is there any birthday tomorrow?")[1]
    assert "relationship" not in r["parsed"]["entities"]


def test_pronoun_resolution():
    r = convo("Where does Rahul Patil stay?", "When is his birthday?")[1]
    assert "18 September 2004" in r["answer"] and r["parsed"]["entities"]["person_id"] == "P004"


def test_pronoun_without_context_is_not_guessed():
    r = convo("When is his birthday?")[0]
    assert "person_id" not in r["parsed"]["entities"]


def test_bare_how_many_reuses_filters():
    r = convo("Any niece birthdays in October?", "How many?")[1]
    assert "2 niece birthdays in October" in r["answer"]
