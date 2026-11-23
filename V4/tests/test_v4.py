import json
from datetime import date
import pytest
import app as A
from data_service import load_people
from llm_nlu import validate_and_ground, llm_parse

DF = load_people()
TODAY = date(2026, 9, 11)


class FakeClient:
    """Stands in for the LLM client so tests need no network or key."""
    def __init__(self, payload=None, error=None):
        self.payload, self.error = payload, error
        self.responses = self.chat = self.completions = self

    def create(self, **kw):
        if self.error:
            raise self.error
        msgs = kw.get("messages") or kw["input"]
        assert "json" in msgs[0]["content"].lower()
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        msg = type("M", (), {"content": text})()
        return type("R", (), {"output_text": text, "choices": [type("C", (), {"message": msg})()]})()


def turn(msg, payload=None, error=None, state=None):
    return A.handle(msg, state or {}, DF, TODAY, llm=FakeClient(payload, error))


def test_paraphrase_via_llm():
    r, _ = turn("Do I need to wish any nephew during September?",
                {"intent": "birthday_search", "entities": {"relationship": "nephew", "plural": True, "month": 9}})
    assert r["nlu_source"] == "llm" and "Rahul Patil" in r["answer"]


def test_name_grounded_to_id():
    r, _ = turn("Rahul coming up soon?", {"intent": "upcoming_birthdays", "entities": {"person_name": "Rahul"}})
    assert r["parsed"]["entities"]["person_id"] == "P004"
    assert "18 September 2004" in r["answer"]


def test_hallucinated_person_rejected():
    r, _ = turn("when is Rahul Patel's birthday", {"intent": "birthday_search", "entities": {"person_name": "Rahul Patel"}})
    assert r["status"] == "empty" and "Patil" not in r["answer"]


def test_person_not_in_sheet():
    r, _ = turn("Zorblax bday?", {"intent": "birthday_search", "entities": {"person_name": "Zorblax"}})
    assert r["status"] == "empty"


def test_ambiguous_llm_name_still_clarifies():
    r, st = turn("Nikhil's birthday?", {"intent": "birthday_search", "entities": {"person_name": "Nikhil"}})
    assert r["status"] == "ambiguous" and st["pending_ids"]


def test_unknown_relationship_not_guessed():
    r, _ = turn("grandma birthday", {"intent": "birthday_search", "entities": {"relationship": "grandmother"}})
    assert r["status"] == "empty"


@pytest.mark.parametrize("payload", [
    {"intent": "birthday_search", "entities": {"month": 13}},
    {"intent": "launch_missiles", "entities": {}},
    {"intent": "birthday_search", "entities": {"dob": "2004-09-18"}},
    {"intent": "birthday_search", "entities": {"day": 5}},
    "not json at all",
])
def test_invalid_output_falls_back_to_rules(payload):
    r, _ = turn("Any nephew birthdays in September?", payload)
    assert r["nlu_source"] == "rules-fallback" and "Rahul Patil" in r["answer"]


def test_api_error_falls_back():
    r, _ = turn("Any nephew birthdays in September?", error=TimeoutError("down"))
    assert r["nlu_source"] == "rules-fallback" and "Rahul Patil" in r["answer"]


def test_no_key_uses_rules(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r, _ = A.handle("Any nephew birthdays in September?", {}, DF, TODAY)
    assert r["nlu_source"] == "rules"


def test_fenced_json_accepted():
    p = llm_parse("x", FakeClient('```json\n{"intent":"unknown","entities":{}}\n```'))
    assert p["intent"] == "unknown"


def test_unsupported_question():
    r, _ = turn("Who is the kindest person?", {"intent": "unknown", "entities": {}})
    assert r["status"] == "unsupported"


def test_invalid_date_still_rejected_by_service():
    r, _ = turn("birthdays on 31 February", {"intent": "birthday_search", "entities": {"day": 31, "month": 2}})
    assert r["status"] == "invalid"


def test_context_still_works_with_llm():
    r1, st = turn("Any nephew birthdays in September?", {"intent": "birthday_search", "entities": {"relationship": "nephew", "month": 9}})
    r2, _ = turn("What about October?", {"intent": "birthday_search", "entities": {"month": 10}}, state=st)
    assert "Nikhil Hegde" in r2["answer"] and r2["parsed"]["entities"]["relationship"] == "Nephew"


def test_grounding_rejects_bad_types():
    with pytest.raises(ValueError):
        validate_and_ground({"intent": "birthday_search", "entities": {"plural": "yes"}}, DF)
