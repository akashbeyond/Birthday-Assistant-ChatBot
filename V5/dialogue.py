"""V3 dialogue layer: carries context between turns. Stored in the Flask session (a plain dict)."""
from __future__ import annotations
import re

# Entities that describe WHAT is being filtered. Carried over only when the new turn omits them.
CARRY_KEYS = ("relationship", "month", "relative_month", "relative_date", "within_days", "place")
# A new value for one of these replaces the whole time filter.
TIME_KEYS = ("month", "relative_month", "relative_date", "within_days", "day")
SUBJECT_KEYS = ("person_id", "person_candidates")


def is_followup(parsed, message="") -> bool:
    """A follow-up names no person and does not restate the task (no word 'birthday'),
    e.g. 'What about October?' or 'How many?'. 'Is there any birthday tomorrow?' is a fresh question."""
    e = parsed["entities"]
    return (parsed["intent"] in ("birthday_search", "count_birthdays", "unknown") and not any(k in e for k in SUBJECT_KEYS)
            and "birthday" not in message.lower())


PRONOUN = re.compile(r"\b(his|her|hers|him|she|he|their|them)\b")


def resolve_pronoun(parsed, state, message) -> bool:
    """'When is his birthday?' right after a single-person answer refers to that same person."""
    e, t = parsed["entities"], message.lower()
    pid = state.get("last_person_id")
    if not pid or e or not PRONOUN.search(t):
        return False
    e["person_id"] = pid
    if re.search(r"\b(where|stay|stays|live|lives|living)\b", t):
        parsed["intent"] = "person_place"
    elif re.search(r"\bage\b|how old", t):
        parsed["intent"] = "person_age"
    else:
        parsed["intent"] = "birthday_search"
    return True


def resolve_clarification(parsed, state, people):
    """If we asked 'which one?' last turn, treat a bare name as the answer.
    Returns ids still matching, or None if this turn is not an answer."""
    pending = state.get("pending_ids")
    if not pending:
        return None
    e = parsed["entities"]
    if "person_id" in e and e["person_id"] in pending:
        return [e["person_id"]]
    if "person_candidates" in e:
        both = [p for p in e["person_candidates"] if p in pending]
        return both or None
    return None


def enrich_with_context(parsed, state, message=""):
    """Fill omitted entities from the previous turn. Only for follow-ups."""
    e = parsed["entities"]
    if state and resolve_pronoun(parsed, state, message):
        return parsed, ["last_person"]
    if not is_followup(parsed, message) or not state:
        return parsed, []
    carried = []
    new_time = any(k in e for k in TIME_KEYS)
    for key in CARRY_KEYS:
        if key in e or key not in state:
            continue
        if new_time and key in TIME_KEYS:   # 'What about October?' replaces September, it must not add to it
            continue
        e[key] = state[key]
        carried.append(key)
    if carried and parsed["intent"] == "unknown":
        parsed["intent"] = state.get("intent", "birthday_search")
    return parsed, carried


def update_state(parsed, result, state):
    """Remember this turn's filters; remember ambiguity so the next turn can answer it."""
    e = parsed["entities"]
    if result["status"] in ("ok", "empty"):
        state = {k: e[k] for k in CARRY_KEYS if k in e}
        state["intent"] = parsed["intent"] if parsed["intent"] != "unknown" else "birthday_search"
        if ("person_id" in e) and len(result["result_ids"]) == 1:
            state["last_person_id"] = result["result_ids"][0]      # lets 'his/her' resolve next turn
    state["pending_ids"] = result["result_ids"] if result["status"] in ("ambiguous", "clarify") else []
    if result["status"] in ("ambiguous", "clarify"):
        state["pending_intent"] = parsed["intent"]
    return state
