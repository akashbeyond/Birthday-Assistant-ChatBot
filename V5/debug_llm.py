import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI, APIStatusError

key = os.getenv("OPENAI_API_KEY", "")
model = os.getenv("OPENAI_MODEL", "gemini-2.5-flash")
print("key starts with:", key[:4], "| key length:", len(key))
print("base url:", os.getenv("OPENAI_BASE_URL"))
print("model:", model)

client = OpenAI()
msgs = [{"role": "user", "content": 'Reply with this JSON: {"ok": true}'}]

for label, extra in [("WITH response_format", {"response_format": {"type": "json_object"}}),
                     ("WITHOUT response_format", {})]:
    try:
        r = client.chat.completions.create(model=model, messages=msgs, **extra)
        print(label, "-> OK:", r.choices[0].message.content)
    except APIStatusError as e:
        print(label, "-> FAILED", e.status_code, e.response.text[:400])