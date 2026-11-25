"""Diagnose your LLM setup. Run:  python check_llm.py        (add --models to list available model names)"""
import os, sys, time
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI, APIStatusError

key = os.getenv("OPENAI_API_KEY", "")
model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
print(f"key starts with: {key[:4]!r}   length: {len(key)}   (a Gemini key starts with 'AIza' or 'AQ.')")
print("base url :", os.getenv("OPENAI_BASE_URL") or "(default OpenAI)")
print("model    :", model)
if not key or key.startswith("your"):
    sys.exit("-> .env still has the placeholder key. Paste your real key after OPENAI_API_KEY= and save the file.")
client = OpenAI(timeout=float(os.getenv("LLM_TIMEOUT", "40")), max_retries=0)
try:
    if "--models" in sys.argv:
        for m in client.models.list():
            print(" ", m.id)
        sys.exit()
    t0 = time.time()
    r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": 'Reply with this JSON: {"ok": true}'}],
                                       response_format={"type": "json_object"})
    print(f"-> OK in {time.time() - t0:.1f}s:", r.choices[0].message.content)
except APIStatusError as e:
    print("-> FAILED", e.status_code, e.response.text[:400])
    hints = {400: "bad key or bad request (is the key real and saved in .env?)", 404: "model name not available: run  python check_llm.py --models",
             429: "free-tier rate/quota limit: wait a minute (or a day) or use another model/key"}
    print("   hint:", hints.get(e.status_code, "see the message above"))
except Exception as e:
    print("-> FAILED:", type(e).__name__, e, "\n   hint: timeout? raise LLM_TIMEOUT in .env or pick a faster model")