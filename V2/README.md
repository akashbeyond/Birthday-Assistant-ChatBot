# CIUX Birthday Assistant - V2: Intent and Entity NLU

Built on V1 (data layer unchanged apart from stripping stray digits from names).

## Files
```
nlu.py  (sentence -> {intent, entities})
service.py (structure -> answer)
app.py  (parse -> execute)
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
Watch the NLU Output panel: check intent/entities BEFORE debugging the query.
Known limitation to log: 'What about October?' and 'When is my nephew's birthday?' (lists all nephews).
