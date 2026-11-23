# CIUX Birthday Assistant - V4: LLM-Assisted NLU, Grounded

Built on V1 (data layer unchanged apart from stripping stray digits from names).

## Files
```
llm_nlu.py (LLM = parser only; validation + grounding)
app.py parse_message(): LLM -> validate -> else rule fallback
```

## Run
```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py   # http://127.0.0.1:5000
```

## Test
```
pytest -q   (uses a fake client, no key needed)
```

## Notes
PowerShell:
  pip install -r requirements.txt
  $env:OPENAI_API_KEY="..."        # never commit this
  $env:OPENAI_MODEL="gpt-4.1-mini"  # default; change if your account has another
  python app.py
No key set => rule parser runs (nlu_source: rules). The panel shows nlu_source: llm | rules | rules-fallback.
