try:                                   # optional: read OPENAI_* settings from a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, jsonify, render_template, request, session
import os
import time
from data_service import load_people
from nlu import parse
from service import execute
from llm_nlu import llm_parse, validate_and_ground
from dialogue import enrich_with_context, resolve_clarification, update_state

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")  # sessions need a key
PEOPLE = load_people()


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
    return {"answer": result["answer"], "status": result["status"], "parsed": parsed,
            "carried_from_context": carried, "nlu_source": source,
            "latency_ms": round((time.perf_counter() - t0) * 1000)}, update_state(parsed, result, state)


@app.post("/api/chat")
def chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    resp, session["state"] = handle(message, session.get("state", {}))
    resp["state"] = session["state"]
    return jsonify(resp)


@app.post("/api/reset")
def reset():
    session.pop("state", None)
    return jsonify(ok=True)


@app.get("/api/health")
def health():
    return jsonify(status="ok", records=len(PEOPLE), version="V4",
                   llm_configured=bool(os.getenv("OPENAI_API_KEY")),
                   model=os.getenv("OPENAI_MODEL", "default"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
