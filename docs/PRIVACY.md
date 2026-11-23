# Privacy note

**Data used.** `people.xlsx` contains 100 *fictional* people (name, nickname, date of birth, place of stay, relationship). No phone numbers, addresses or other sensitive attributes are stored.

**What the system stores.**
- The spreadsheet, on the local machine only.
- Per-browser dialogue state in a signed Flask session cookie (last filters, last person ID, pending candidates). It holds IDs and filter values, not message history, and is cleared by Reset or a page reload.
- No database, no conversation log. Latency and parse info are shown in the debug panel only.

**What leaves the machine (V4/V5, LLM enabled).** Only the user's sentence and a fixed system prompt are sent to the LLM provider. The spreadsheet is never sent. The speech transcript (V5) is produced by the browser's speech service, which in Chrome/Edge may send audio to the browser vendor's servers. Free LLM tiers may log or train on prompts, so do not type real personal details.

**Secrets.** API keys live only in environment variables or a git-ignored `.env`. `FLASK_SECRET` must be set to a random value outside development.

**Do not publish.** `.env`, `.venv`, any real contact data. Submit the synthetic workbook only.

**If this were deployed with real family information, these become mandatory:**
1. Authentication and per-user data separation before any query.
2. HTTPS everywhere and a production WSGI server (not Flask debug mode).
3. Encrypted storage and access control for the data (a database instead of a loose spreadsheet), plus backups.
4. Informed consent from the people listed, data minimisation, and a deletion path.
5. A provider with a no-training/zero-retention agreement, or a local model, since names and birthdays would reach the LLM in prompts.
6. Logging policy: never log raw messages containing personal data; rotate and restrict logs.
7. Explicit opt-in for reminders/notifications and calendar integrations.
