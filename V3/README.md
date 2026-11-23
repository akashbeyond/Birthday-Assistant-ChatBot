# CIUX Birthday Assistant - V3: Dialogue State and Clarification

Built on V1 (data layer unchanged apart from stripping stray digits from names).

## Files
```
dialogue.py (carry-over, clarification answers, state)
service.py now asks 'Which one?' for singular ambiguous questions
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
pytest -q
```

## Notes
Try: 'Any nephew birthdays in September?' -> 'What about October?'
Try: 'When is my nephew's birthday?' -> 'Nikhil' (2 nephews match, so it asks again) -> 'Nikhil Hegde'
Reload page or press Reset to clear context.
