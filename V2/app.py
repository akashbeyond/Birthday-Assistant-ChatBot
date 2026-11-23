from flask import Flask, jsonify, render_template, request
from data_service import load_people
from nlu import parse
from service import execute

app = Flask(__name__)
PEOPLE = load_people()


@app.get("/")
def index():
    return render_template("index.html", record_count=len(PEOPLE))


@app.post("/api/chat")
def chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    parsed = parse(message, PEOPLE)      # 1. language -> structure
    result = execute(parsed, PEOPLE)     # 2. structure -> answer
    return jsonify(answer=result["answer"], status=result["status"], parsed=parsed)


@app.get("/api/health")
def health():
    return jsonify(status="ok", records=len(PEOPLE), version="V2")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
