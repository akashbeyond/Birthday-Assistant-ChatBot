# CIUX Birthday Assistant (UE24CS3540) - V1 to V5

A conversational interface over a spreadsheet of 100 fictional people, built one capability at a time.
Facts always come from `data/people.xlsx`; the LLM and the voice layer are never a source of truth.

| Folder | Version | Adds |
|---|---|---|
| `V1` | Deterministic rules | Chat UI, Flask `/api/chat`, keyword rules, pandas filters |
| `V2` | Intent + entities | `nlu.py` (sentence to intent/entities), `service.py` (query + reply) |
| `V3` | Dialogue state | `dialogue.py`: follow-ups, pronouns, "which one?" clarification, Reset |
| `V4` | LLM-assisted NLU | `llm_nlu.py`: LLM parses to JSON only, grounded against the sheet, rule fallback |
| `V5` | Voice | Speak button (SpeechRecognition) + read-aloud (SpeechSynthesis); backend = V4 |

Also: `TESTING.md` (40 utterances, results, metrics), `eval/` (test runner), `docs/` (architecture, privacy, reflection, journal).

## 1. One-time setup (Windows / PowerShell)

Requires Python 3.11+ and Chrome or Edge (for voice).

```powershell
cd birthday-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r V5\requirements.txt      # superset of every version's requirements
```

## 2. Run any version

```powershell
cd V1          # or V2, V3, V4, V5
python app.py  # open http://127.0.0.1:5000   (Ctrl+C to stop; use one version at a time, they share port 5000)
```

V1-V3 need no key. V4/V5 run without a key too (rule parser, `nlu_source: rules`); add a key to enable the LLM.

## 3. Turn on the LLM (V4 and V5)

Free option: Google Gemini. Get a key at https://aistudio.google.com (Get API key).

```powershell
cd V5
copy .env.example .env      # then open .env and paste your key; .env is git-ignored
python app.py
```

Check `http://127.0.0.1:5000/api/health` shows `"llm_configured": true`. Ask
"Do I need to wish any nephew during September?" - the right-hand panel must show `nlu_source: llm`.
`rules-fallback` means the key was seen but the call failed: read the red error in the terminal (wrong key/model/URL, or rate limit).
For OpenAI instead of Gemini, edit `.env` (instructions inside the file). Never commit or share a real key.

## 4. Run the tests

```powershell
cd V3 ; python -m pytest -q ; cd ..     # use "python -m pytest": pytest.exe may be blocked by Windows policy
```
Expected: V2 12, V3 24, V4 42, V5 42 passed (V1 has its own tests).

## 5. Run the 40-utterance evaluation (fills `TESTING.md`)

```powershell
python eval/run_eval.py                       # V1-V4, no key needed
python eval/run_eval.py --llm                 # also runs V4 with your LLM key (reads V4\.env); takes ~5 min on a free tier
```
Then complete the two manual tables at the bottom of `TESTING.md` (voice, peer test).

## 6. Test voice (V5)

Run V5 in Chrome/Edge, press Speak, allow the microphone. The "Heard:" line shows the transcript, so you can
tell speech-recognition errors from NLU errors. Untick "Read answers aloud" and confirm text behaviour is identical.

## 7. Submission checklist (manual section 5)

- [ ] Git repo with V1-V5 folders (`git init`, `git add .`, `git commit`; `.gitignore` already excludes `.env` and `.venv`)
- [ ] One screenshot (or short video) of a successful test per version: V1-V5
- [ ] `TESTING.md`: re-run with `--llm`, fill the voice and peer-test tables
- [ ] `docs/REFLECTION.md`: rewrite in your own words using your own observations
- [ ] `docs/LEARNING_JOURNAL.md` (Appendix C): verify against what you saw
- [ ] `docs/architecture.png` + `docs/ARCHITECTURE.md`, `docs/PRIVACY.md`
- [ ] Confirm no real family data and no API key anywhere in the repo

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pytest.exe ... blocked` | `python -m pytest -q` |
| `llm_configured: false` | `.env` missing/misnamed (must be `V5\.env`), or the key line still says `your-gemini-key` |
| `nlu_source: rules-fallback` | Terminal shows why; usually wrong `OPENAI_MODEL`/`OPENAI_BASE_URL` or rate limit |
| Speak does nothing | Use Chrome/Edge on `http://127.0.0.1:5000`; allow the mic |
| `Address already in use` | Another version is still running; Ctrl+C it |
