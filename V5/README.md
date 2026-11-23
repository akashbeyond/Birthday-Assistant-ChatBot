# CIUX Birthday Assistant - V5: Voice Interface

V4 backend unchanged. Only `templates/index.html` and `static/chat.js` changed.

- Speak button -> browser SpeechRecognition (en-IN) -> same `ask()` -> `/api/chat`
- Answers are shown as text AND read aloud (checkbox to turn off)
- 'Heard: ...' line shows the transcript, so you can tell ASR errors from NLU errors

Use Chrome or Edge at http://127.0.0.1:5000 (localhost is allowed to use the microphone). Allow mic permission.

## Test
`pytest -q` (backend). Voice must be tested manually in the browser.
