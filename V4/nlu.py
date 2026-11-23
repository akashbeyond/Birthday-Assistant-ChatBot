"""V2 NLU: sentence -> {intent, entities}. No data lookup and no answers here."""
from __future__ import annotations
import calendar
import re

MONTHS = {n.lower(): i for i, n in enumerate(calendar.month_name) if n}
MONTHS.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
               "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12})

RELATIONSHIP_ALIASES = {
    "wife": "Wife", "spouse": "Wife",
    "father": "Father", "dad": "Father", "appa": "Father",
    "mother": "Mother", "mom": "Mother", "amma": "Mother",
    "brother": "Brother", "brothers": "Brother", "bro": "Brother",
    "sister": "Sister", "sisters": "Sister", "sis": "Sister",
    "brother-in-law": "Brother-in-law", "brothers-in-law": "Brother-in-law",
    "sister-in-law": "Sister-in-law", "sisters-in-law": "Sister-in-law",
    "nephew": "Nephew", "nephews": "Nephew",
    "niece": "Niece", "nieces": "Niece",
    "uncle": "Uncle", "uncles": "Uncle",
    "aunt": "Aunt", "aunts": "Aunt",
    "cousin": "Cousin", "cousins": "Cousin",
    "friend": "Friend", "friends": "Friend",
    "colleague": "Colleague", "colleagues": "Colleague",
    "student": "Student", "students": "Student",
    "neighbour": "Neighbour", "neighbor": "Neighbour",
    "neighbours": "Neighbour", "neighbors": "Neighbour",
}
SINGULAR_EXCEPTIONS = {"sis"}  # ends with 's' but is singular


def has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(phrase.lower()) + r"(?![\w-])", text) is not None


def _find_person(text, people):
    """Return ('id', pid) | ('candidates', [pids]) | None. Full name beats first name/nickname."""
    best = None
    for _, r in people.iterrows():
        full = r["Name"].lower()
        if has(text, full) and (best is None or len(full) > best[0]):
            best = (len(full), r["Person_ID"])
    if best:
        return "id", best[1]
    ids = []
    for _, r in people.iterrows():
        aliases = {r["Name"].lower().split()[0], r["Nickname"].lower()}
        if any(a and len(a) >= 3 and has(text, a) for a in aliases):
            ids.append(r["Person_ID"])
    if len(ids) == 1:
        return "id", ids[0]
    if ids:
        return "candidates", ids
    return None


def parse(message: str, people) -> dict:
    text = re.sub(r"\s+", " ", (message or "").strip().lower())
    e: dict = {}
    if not text:
        return {"intent": "unknown", "entities": e}
    if text in {"help", "examples"} or "what can i ask" in text:
        return {"intent": "help", "entities": e}

    # --- entities -------------------------------------------------------
    person = _find_person(text, people)
    if person and person[0] == "id":
        e["person_id"] = person[1]
    elif person:
        e["person_candidates"] = person[1]

    for alias in sorted(RELATIONSHIP_ALIASES, key=len, reverse=True):
        if has(text, alias):
            e["relationship"] = RELATIONSHIP_ALIASES[alias]
            if alias.endswith("s") and alias not in SINGULAR_EXCEPTIONS:
                e["plural"] = True
            break

    for place in sorted(people["Place_of_Stay"].unique(), key=len, reverse=True):
        if place and has(text, place.lower()):
            e["place"] = place
            break

    if has(text, "next month"):
        e["relative_month"] = "next"
    elif has(text, "this month"):
        e["relative_month"] = "this"
    else:
        for name in sorted(MONTHS, key=len, reverse=True):
            if has(text, name):
                e["month"] = MONTHS[name]
                break

    names = "|".join(sorted(MONTHS, key=len, reverse=True))
    m = (re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({names})\b", text)
         or re.search(rf"\b({names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)", text))
    if m:
        a, b = m.groups()
        day, mon = (int(a), b) if a.isdigit() else (int(b), a)
        e["day"], e["month"] = day, MONTHS[mon]
        e.pop("relative_month", None)

    n = re.search(r"\b(?:next|within|coming)\s+(\d{1,3})\s+days?\b", text)
    if n:
        e["within_days"] = int(n.group(1))
    elif has(text, "day after tomorrow"):
        e["relative_date"] = "day_after_tomorrow"
    elif has(text, "tomorrow"):
        e["relative_date"] = "tomorrow"
    elif has(text, "today"):
        e["relative_date"] = "today"
    elif has(text, "this week"):
        e["relative_date"] = "this_week"
    elif has(text, "next week"):
        e["relative_date"] = "next_week"

    # --- intent ---------------------------------------------------------
    place_q = re.search(r"\b(where|stay|stays|staying|live|lives|living)\b", text)
    has_person = "person_id" in e or "person_candidates" in e
    if has_person and place_q:
        intent = "person_place"
    elif has_person and re.search(r"\bage\b|how old", text):
        intent = "person_age"
    elif "place" in e and place_q and not has_person:
        intent = "place_search"
    elif re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", text):
        intent = "count_birthdays"
    elif re.search(r"\bupcoming\b|\bcoming birthdays\b|\bsoon\b", text):
        intent = "upcoming_birthdays"
        if not ({"within_days", "relative_date", "month", "relative_month"} & e.keys()):
            e["within_days"] = 30
    elif e:
        intent = "birthday_search"
    else:
        intent = "unknown"
    return {"intent": intent, "entities": e}
