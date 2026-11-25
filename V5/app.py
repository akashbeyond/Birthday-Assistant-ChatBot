try:                                   # optional: read OPENAI_* settings from a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import json
import os
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from data_service import load_people
from nlu import parse
from service import execute
from llm_nlu import llm_parse, validate_and_ground, llm_reply, reply_is_grounded
from dialogue import enrich_with_context, resolve_clarification, update_state

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")  # sessions need a key
PEOPLE = load_people()

MAX_MESSAGE_CHARS = 300          # longer input is cut off (basic abuse / cost safeguard)
ESCALATE_AFTER = 2               # consecutive failed turns before handing off to a human
LOG_PATH = Path(__file__).resolve().parent / "logs" / "escalations.jsonl"
HANDOFF = ("\n\nI'm not able to help with this. Please check people.xlsx directly "
           "or ask the owner of this list.")


def _failed(result, parsed):
    """A turn failed when the question is unsupported or names someone/something not in the sheet."""
    ents = parsed["entities"]
    return result["status"] == "unsupported" or any(
        k in ents for k in ("unknown_person", "unknown_relationship", "unknown_place"))


def _log_escalation(message, status):
    """Record only escalated turns (time, question, status) so the owner can review what the assistant could not do."""
    try:
        LOG_PATH.parent.mkdir(exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"),
                                "message": message, "status": status}) + "\n")
    except OSError as exc:
        app.logger.warning("could not write escalation log: %s", exc)


@app.get("/")
def index():
    session.pop("state", None)
    return render_template("index.html", record_count=len(PEOPLE))


def parse_message(message, people, llm=None):
    """LLM first (if a key is configured), validated + grounded; rule parser as fallback."""
    if llm is None and not os.getenv("OPENAI_API_KEY"):
        return parse(message, people), "rules"
    try:
        return validate_and_ground(llm_parse(message, llm), people), "llm"
    except Exception as exc:               # API down, bad JSON, schema violation, ...
        app.logger.warning("LLM NLU failed (%s); using rule parser", exc)
        return parse(message, people), "rules-fallback"


def handle(message, state, people=PEOPLE, today=None, llm=None):
    """One conversational turn. Pure function of (message, state) -> (response, new_state)."""
    t0 = time.perf_counter()
    parsed, source = parse_message(message, people, llm)
    answered = resolve_clarification(parsed, state, people)
    if answered is not None:                      # user is answering our "which one?"
        key = "person_id" if len(answered) == 1 else "person_candidates"
        parsed["entities"] = {key: answered[0] if len(answered) == 1 else answered}
        parsed["intent"] = state.get("pending_intent", "birthday_search")
        carried = ["clarification"]
    else:
        parsed, carried = enrich_with_context(parsed, state, message)
    result = execute(parsed, people, today)
    answer, reply_source = result["answer"], "template"
    if os.getenv("LLM_REPLY") == "1" and result["status"] in ("ok", "ambiguous", "empty", "invalid"):
        try:                                   # optional: LLM rewords the grounded answer; guard rejects invented facts
            text = llm_reply(message, result["answer"], llm)
            if reply_is_grounded(text, result["answer"], people):
                answer, reply_source = text, "llm"
            else:
                reply_source = "template (guard rejected LLM wording)"
        except Exception as exc:
            app.logger.warning("LLM reply failed (%s); using template", exc)
    streak = state.get("fail_streak", 0) + 1 if _failed(result, parsed) else 0
    escalated = streak >= ESCALATE_AFTER
    if escalated:                                  # human escalation: stop guessing, point to a person / the sheet
        answer += HANDOFF
        _log_escalation(message, result["status"])
    new_state = update_state(parsed, result, state)
    new_state["fail_streak"] = streak
    return {"answer": answer, "grounded_answer": result["answer"], "reply_source": reply_source,
            "status": result["status"], "escalated": escalated, "parsed": parsed,
            "carried_from_context": carried, "nlu_source": source,
            "latency_ms": round((time.perf_counter() - t0) * 1000)}, new_state


@app.post("/api/chat")
def chat():
    message = str((request.get_json(silent=True) or {}).get("message", ""))[:MAX_MESSAGE_CHARS]
    resp, session["state"] = handle(message, session.get("state", {}))
    resp["state"] = session["state"]
    return jsonify(resp)


@app.post("/api/reset")
def reset():
    session.pop("state", None)
    return jsonify(ok=True)


@app.get("/api/health")
def health():
    return jsonify(status="ok", records=len(PEOPLE), version="V5",
                   llm_configured=bool(os.getenv("OPENAI_API_KEY")),
                   model=os.getenv("OPENAI_MODEL", "default"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")