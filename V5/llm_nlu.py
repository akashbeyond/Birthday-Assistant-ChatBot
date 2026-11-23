"""V4: the LLM is ONLY a semantic parser (sentence -> JSON). It never sees the spreadsheet and never answers.
Everything it returns is validated and grounded against the sheet before service.py uses it."""
from __future__ import annotations
import json
import os
import re

from nlu import RELATIONSHIP_ALIASES, _find_person

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")   # for Gemini set OPENAI_MODEL=gemini-2.5-flash
INTENTS = {"birthday_search", "count_birthdays", "upcoming_birthdays", "person_place",
           "person_age", "place_search", "help", "unknown"}
REL_DATES = {"today", "tomorrow", "day_after_tomorrow", "this_week", "next_week"}

SYSTEM = """You are an NLU parser for a personal birthday assistant. Output ONE JSON object and nothing else:
{"intent": <intent>, "entities": {...}}
Intents: birthday_search (list/lookup birthdays), count_birthdays (how many), upcoming_birthdays (soon / upcoming),
person_place (where does a PERSON stay), person_age (how old is a PERSON), place_search (who stays in a PLACE),
help, unknown (anything else, e.g. opinions or small talk).
Entities (include only those the user actually said; never guess):
 person_name: string, exactly as the user wrote it
 relationship: string, e.g. nephew, niece, wife, uncle, sister-in-law, cousin
 plural: true if the user asks about several people of that relationship, false if about one
 month: integer 1-12 | day: integer day of month (as written, even if impossible)
 relative_month: "this" or "next" | relative_date: today, tomorrow, day_after_tomorrow, this_week, next_week
 within_days: integer | place: string
Rules: NEVER answer the question. NEVER invent names, dates or birthdays. Do not resolve dates yourself.
If unsure, use intent "unknown" with empty entities.
Examples:
"Do I need to wish any nephew during September?" -> {"intent":"birthday_search","entities":{"relationship":"nephew","plural":true,"month":9}}
"Rahul coming up soon?" -> {"intent":"upcoming_birthdays","entities":{"person_name":"Rahul"}}"""


def build_client():
    from openai import OpenAI          # imported lazily so V1-V3 behaviour needs no package or key
    return OpenAI(timeout=float(os.getenv("LLM_TIMEOUT", "40")), max_retries=1)   # reads OPENAI_API_KEY and OPENAI_BASE_URL from the environment


def llm_parse(message: str, client=None) -> dict:
    client = client or build_client()
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}],
        response_format={"type": "json_object"},
    )
    txt = re.sub(r"^```(?:json)?|```$", "", r.choices[0].message.content.strip(), flags=re.M).strip()
    return json.loads(txt)


def _int(v, lo, hi, name):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        if isinstance(v, str) and v.isdigit() and lo <= int(v) <= hi:
            return int(v)
        raise ValueError(f"{name} out of range: {v!r}")
    return v


def ground_person(name: str, people):
    """Map an LLM-supplied name onto the sheet. A multi-word name must match a full name exactly:
    'Rahul Patel' must NOT silently become 'Rahul Patil'."""
    n = re.sub(r"\s+", " ", name.strip().lower())
    for _, r in people.iterrows():
        if r["Name"].lower() == n:
            return {"person_id": r["Person_ID"]}
    if len(n.split()) >= 2:
        return {"unknown_person": name}
    found = _find_person(n, people)
    if found is None:
        return {"unknown_person": name}
    return {"person_id": found[1]} if found[0] == "id" else {"person_candidates": found[1]}


def validate_and_ground(raw: dict, people) -> dict:
    """Raise ValueError on anything malformed; otherwise return {intent, entities} in the V2/V3 format."""
    if not isinstance(raw, dict) or raw.get("intent") not in INTENTS:
        raise ValueError("bad intent")
    ents = raw.get("entities") or {}
    if not isinstance(ents, dict):
        raise ValueError("entities not an object")
    out: dict = {}
    for k, v in ents.items():
        if v is None or v == "":
            continue
        if k == "person_name":
            out.update(ground_person(str(v), people))
        elif k == "relationship":
            canon = RELATIONSHIP_ALIASES.get(str(v).strip().lower())
            if canon is None:
                canon = next((x for x in people["Relationship"].unique() if x.lower() == str(v).strip().lower()), None)
            if canon is None:
                out["unknown_relationship"] = str(v)
            else:
                out["relationship"] = canon
        elif k == "plural":
            if not isinstance(v, bool):
                raise ValueError("plural must be boolean")
            if v:
                out["plural"] = True
        elif k == "month":
            out["month"] = _int(v, 1, 12, "month")
        elif k == "day":
            out["day"] = _int(v, 1, 99, "day")      # impossible days are rejected by service.py with a clear message
        elif k == "within_days":
            out["within_days"] = _int(v, 1, 366, "within_days")
        elif k == "relative_month":
            if v not in ("this", "next"):
                raise ValueError("bad relative_month")
            out["relative_month"] = v
        elif k == "relative_date":
            if v not in REL_DATES:
                raise ValueError("bad relative_date")
            out["relative_date"] = v
        elif k == "place":
            hit = next((p for p in people["Place_of_Stay"].unique() if p and p.lower() == str(v).strip().lower()), None)
            out["place" if hit else "unknown_place"] = hit or str(v)
        else:
            raise ValueError(f"unexpected entity {k!r}")
    if "day" in out and "month" not in out:
        raise ValueError("day without month")
    if raw["intent"] == "upcoming_birthdays" and not ({"within_days", "relative_date", "month", "relative_month"} & out.keys()):
        out["within_days"] = 30
    return {"intent": raw["intent"], "entities": out}

# ---------- Optional: natural-language replies. The LLM only rewords facts the query service already found. ----------
REPLY_SYSTEM = """You are the friendly voice of a personal birthday assistant. Rewrite the FACTS as a short, natural reply to the user's question.
Rules: use ONLY the facts given. Never add, change or guess any name, date, number, place or relationship. Keep every name and date exactly as written.
At most 3 sentences, or a short bullet list when there are many people. Write numbers as digits. Plain text, no markdown headings."""


def llm_reply(question: str, facts: str, client=None) -> str:
    client = client or build_client()
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": REPLY_SYSTEM},
                  {"role": "user", "content": f"Question: {question}\nFACTS:\n{facts}"}],
    )
    return r.choices[0].message.content.strip()


NUMBER_WORDS = {"two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"}


def reply_is_grounded(reply: str, facts: str, people) -> bool:
    """Reject LLM wording containing a number, number word or person name that is not in the facts.
    A count of the listed people (bullet lines) is allowed, since the model may say '3 nephews'."""
    allowed = {int(x) for x in re.findall(r"\d+", facts)} | {facts.count("•")}
    if not {int(x) for x in re.findall(r"\d+", reply)} <= allowed:
        return False
    if NUMBER_WORDS & set(re.findall(r"[a-z]+", reply.lower())):
        return False
    low, fl = reply.lower(), facts.lower()
    for name in people["Name"]:
        full = name.lower()
        first = full.split()[0]
        if (full in low and full not in fl) or (len(first) >= 3 and re.search(rf"\b{re.escape(first)}\b", low)
                                                and not re.search(rf"\b{re.escape(first)}\b", fl)):
            return False
    return True