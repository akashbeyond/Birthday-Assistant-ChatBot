# Appendix C: Version Learning Journal

> Pre-filled from the automated runs in `TESTING.md`. Verify each cell against what you actually observed and add your own notes.

| Version | What worked? | What failed? | Why? | What changed in next version? |
|---|---|---|---|---|
| V1 | Direct questions (10/10); facts always matched the sheet | Paraphrases (7/10), context, ambiguity (1/10); "Rahul Patel" answered as Rahul Patil | One rule function mixes parsing, filtering and wording; keywords must match exactly | Split NLU from querying: intents + entities |
| V2 | Modular, testable; intent/entity visible in the trace; 31/40 overall | "What about October?", "How many?" (answered 100), singular "my nephew" lists all, "his birthday" | Each turn is parsed in isolation; no memory | Dialogue state, clarification, pronouns, Reset |
| V3 | Follow-ups, clarification (2/2), pronouns; 35/40 overall | "in the coming month", off-topic and unknown-action questions answered as birthday queries, "Rahul Patel" guessed | Keyword rules cannot understand paraphrase or reject unsupported requests | LLM as parser with validation, grounding and fallback |
| V4 | (fill after your `--llm` run) paraphrases, unsupported questions, unknown names rejected | (fill in) | LLM improves language coverage, not factual accuracy; grounding provides the facts | Add voice channel |
| V5 | (fill after voice test) text and speech share one backend | (fill in: ASR errors on names/places) | Speech recognition errors occur before NLU | Evaluation, documentation, privacy |

## Final reflection questions

1. **First conversational rather than merely searchable?** V3: it remembers context and asks "which one?" when ambiguous.
2. **What did the LLM improve, and what did it not?** It improves understanding of wording variety. It does not make facts correct; grounding and validation do.
3. **Why is dialogue state dangerous if carried forward too aggressively?** Stale filters leak into new questions ("Is there any birthday tomorrow?" becoming "nephew birthdays tomorrow"). V3 carries only for follow-ups that omit the subject and the word "birthday", and Reset clears it.
4. **Language-understanding vs data-model failures?** Understanding: P10 "coming month", off-topic and unsupported actions. Data model: two people marked Wife, two or more people sharing a first name, stray digits in names ("Sneha Sharma4"), which `data_service.py` cleans.
5. **Privacy and security controls if real data were used?** See `PRIVACY.md`: authentication, HTTPS, encrypted storage, consent, no-retention LLM provider, log hygiene.
