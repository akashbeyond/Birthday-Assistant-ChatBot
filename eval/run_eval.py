"""Run the 40-utterance test set against V1-V4 and write results + TESTING.md.

    python eval/run_eval.py              # rule mode, no API key needed (V4 uses its rule fallback)
    python eval/run_eval.py --llm        # also run V4 with your LLM key (reads V4/.env or the environment)
Each version runs in its own subprocess because the versions share module names (app, nlu, service ...).
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
from cases import CASES, TODAY  # noqa: E402

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"


# ------------------------------------------------------------------ worker (one version)
def worker(version: str, use_llm: bool, pause: float):
    vdir = ROOT / version
    os.chdir(vdir)
    sys.path.insert(0, str(vdir))
    if not use_llm:
        for k in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
            os.environ.pop(k, None)
    import pandas as pd
    from data_service import load_people
    df = load_people()
    raw = pd.read_excel(vdir / "data" / "people.xlsx", sheet_name="People")
    dob_by_name = {}
    for n, d in zip(list(df["Name"]) + list(raw["Name"]), list(df["DOB"]) + list(pd.to_datetime(raw["DOB"]))):
        dob_by_name[str(n)] = d
    place_by_name = dict(zip(df["Name"], df["Place_of_Stay"])) | dict(zip(raw["Name"], raw["Place_of_Stay"]))
    names = sorted(set(df["Name"]) | set(raw["Name"]), key=len, reverse=True)

    if version == "V1":
        from rules import answer_question
        def turn(msg, state):
            return answer_question(df, msg, TODAY)["answer"], None, state, None
    elif version == "V2":
        from nlu import parse
        from service import execute
        def turn(msg, state):
            p = parse(msg, df)
            return execute(p, df, TODAY)["answer"], p, state, "rules"
    else:
        import app as A
        def turn(msg, state):
            r, state = A.handle(msg, state, df, TODAY)
            return r["answer"], r["parsed"], state, r.get("nlu_source")

    def facts_check(answer):
        ok = total = 0
        for name, d in re.findall(rf"• (.+?) — (\d{{2}} {MONTH})", answer):
            total += 1; ok += name in dob_by_name and dob_by_name[name].strftime("%d %B") == d
        for name, d in re.findall(rf"(.+?)'s birthday is (\d{{2}} {MONTH} \d{{4}})", answer):
            total += 1; ok += name in dob_by_name and dob_by_name[name].strftime("%d %B %Y") == d
        for name, pl in re.findall(r"(.+?) stays in (\w+)\.", answer):
            total += 1; ok += place_by_name.get(name) == pl
        return ok, total

    out, sources = [], set()
    for c in CASES:
        state, lat, ans, parsed = {}, [], "", None
        for msg in c["turns"]:
            if msg == "__reset__":
                state = {}; continue
            t0 = time.perf_counter()
            try:
                ans, parsed, state, src = turn(msg, state)
            except Exception as exc:  # a crash is a failed test, not a stopped run
                ans, parsed, src = f"ERROR: {exc}", None, None
            lat.append((time.perf_counter() - t0) * 1000)
            if src: sources.add(src)
            if use_llm: time.sleep(pause)
        low = ans.lower()
        checks = [all(s.lower() in low for s in c.get("contains", [])),
                  not any(s.lower() in low for s in c.get("not_contains", [])),
                  ("any_of" not in c) or any(s.lower() in low for s in c["any_of"]),
                  (not c.get("no_names")) or not any(n.lower() in low for n in names)]
        res = dict(id=c["id"], passed=all(checks), answer=ans, ms=sum(lat) / max(len(lat), 1))
        if version != "V1":
            if "intent" in c:
                res["intent_ok"] = bool(parsed) and parsed["intent"] == c["intent"]
            if "entities" in c:
                got = (parsed or {}).get("entities", {})
                res["entity_hits"] = [got.get(k) == v for k, v in c["entities"].items()]
        res["facts"] = facts_check(ans)
        out.append(res)
    print(json.dumps(dict(version=version, sources=sorted(sources), results=out)))


# ------------------------------------------------------------------ orchestration + report
def run_version(version, use_llm, pause):
    env = os.environ.copy()
    p = subprocess.run([sys.executable, __file__, "--worker", version, "--llm" if use_llm else "--rules",
                        "--pause", str(pause)], capture_output=True, text=True, env=env)
    if p.returncode:
        sys.exit(f"{version} failed:\n{p.stderr}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def summarise(run):
    res = {r["id"]: r for r in run["results"]}
    cats = {}
    for c in CASES:
        cats.setdefault(c["cat"], []).append(res[c["id"]]["passed"])
    allr = list(res.values())
    intent = [r["intent_ok"] for r in allr if "intent_ok" in r]
    ents = [h for r in allr for h in r.get("entity_hits", [])]
    fok = sum(r["facts"][0] for r in allr); ftot = sum(r["facts"][1] for r in allr)
    clar = [res[i]["passed"] for i in ("A01", "A02")]
    return dict(cats={k: (sum(v), len(v)) for k, v in cats.items()}, total=(sum(r["passed"] for r in allr), len(allr)),
                intent=(sum(intent), len(intent)) if intent else None, entity=(sum(ents), len(ents)) if ents else None,
                clar=(sum(clar), len(clar)), facts=(fok, ftot), ms=sum(r["ms"] for r in allr) / len(allr))


def pct(t):
    return "n/a (V1 exposes no NLU)" if t is None else f"{t[0]}/{t[1]} ({100 * t[0] / max(t[1], 1):.0f}%)"


def write_report(runs):
    names = list(runs)
    S = {n: summarise(runs[n]) for n in names}
    L = ["# TESTING.md", "",
         "Generated by `python eval/run_eval.py`. Fixed clock: **today = 2026-09-11** (so results are repeatable).",
         "Dataset: synthetic `people.xlsx` (100 fictional people). Pass/fail is judged on the final assistant reply.", "",
         "## How to reproduce", "```", "python eval/run_eval.py            # rule mode, no key needed",
         "python eval/run_eval.py --llm      # adds V4 with your LLM (V4/.env or environment variables)", "```", "",
         "Columns: " + ", ".join(f"**{n}**" for n in names) + ". `V4 (rules)` is V4 running its rule-parser fallback "
         "(no key set), i.e. the V3 parser plus the V4 plumbing. `V4 (LLM)` appears only after a `--llm` run. "
         "V5 has the same backend as V4; its voice layer is tested manually (see end).", "",
         "## Summary", "", "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for cat in ["Direct", "Paraphrase", "Context", "Ambiguous/Unsupported"]:
        L.append(f"| Task success: {cat} | " + " | ".join(pct(S[n]['cats'][cat]) for n in names) + " |")
    L.append("| **Task success: all 40** | " + " | ".join("**" + pct(S[n]['total']) + "**" for n in names) + " |")
    L.append("| Intent accuracy | " + " | ".join(pct(S[n]['intent']) for n in names) + " |")
    L.append("| Entity accuracy | " + " | ".join(pct(S[n]['entity']) for n in names) + " |")
    L.append("| Clarification success (A01, A02) | " + " | ".join(pct(S[n]['clar']) for n in names) + " |")
    L.append("| Grounded factuality (dates/places in replies match the sheet) | " + " | ".join(pct(S[n]['facts']) for n in names) + " |")
    L.append("| Avg latency per test (ms, local; LLM column includes the API call) | " + " | ".join(f"{S[n]['ms']:.1f}" for n in names) + " |")
    L += ["", "Metric definitions follow section 4.2 of the manual. Intent/entity accuracy are judged only on the cases "
          "that declare an expected intent/entities (see `eval/cases.py`).", "",
          "## Per-utterance results", "", "| ID | Category | Utterance(s) | Expected behaviour | " + " | ".join(names) + " |",
          "|---|---|---|---|" + "---|" * len(names)]
    byid = {n: {r["id"]: r for r in runs[n]["results"]} for n in names}
    for c in CASES:
        utt = " → ".join(t if t != "__reset__" else "[Reset]" for t in c["turns"]).replace("|", "\\|")
        L.append(f"| {c['id']} | {c['cat']} | {utt} | {c['note']} | " +
                 " | ".join("PASS" if byid[n][c["id"]]["passed"] else "FAIL" for n in names) + " |")
    L += ["", "## Failure log (what the failing versions actually said)", ""]
    for n in names:
        fails = [r for r in runs[n]["results"] if not r["passed"]]
        L.append(f"### {n}: {len(fails)} failing")
        for r in fails:
            first = r["answer"].replace("\n", " ⏎ ")[:150]
            L.append(f"- **{r['id']}** → {first}")
        L.append("")
    L += ["## Manual test: voice (V5) — fill in after testing in Chrome/Edge", "",
          "Speak each utterance once. Record what the *Heard:* line showed before blaming the NLU.", "",
          "| # | Spoken utterance | Heard (transcript) | Transcript correct? | Final answer correct? | Fault layer (ASR / NLU / context / data) |",
          "|---|---|---|---|---|---|"]
    for i, u in enumerate(["Any birthdays tomorrow?", "When is Rahul Patil's birthday?", "Any nephew birthdays in September?",
                           "What about October?", "Where does Ananya Patil stay?", "Who stays in Hassan?",
                           "How many birthdays are there next month?", "When is my wife's birthday?",
                           "When is Nikhil's birthday?", "Birthdays in Shivamogga"], 1):
        L.append(f"| {i} | {u} |  |  |  |  |")
    L += ["", "Voice recognition success = rows with 'Transcript correct? = yes' / 10.", "",
          "## Manual test: peer usability (3-5 classmates) — fill in", "",
          "| Peer | Clarity (1-5) | Error recovery (1-5) | Trust (1-5) | Ease of use (1-5) | Comment |", "|---|---|---|---|---|---|",
          "| 1 |  |  |  |  |  |", "| 2 |  |  |  |  |  |", "| 3 |  |  |  |  |  |", ""]
    (ROOT / "TESTING.md").write_text("\n".join(L), encoding="utf-8")
    (EVAL / "results.json").write_text(json.dumps({n: dict(summary=S[n], results=runs[n]["results"]) for n in names}, indent=1), encoding="utf-8")
    return S


def main():
    llm = "--llm" in sys.argv
    pause = float(sys.argv[sys.argv.index("--pause") + 1]) if "--pause" in sys.argv else 6.5
    runs = {}
    for v in ("V1", "V2", "V3", "V4"):
        label = "V4 (rules)" if v == "V4" else v
        runs[label] = run_version(v, False, 0)
    if llm:
        runs["V4 (LLM)"] = run_version("V4", True, pause)
        srcs = runs["V4 (LLM)"]["sources"]
        print("V4 LLM run, nlu sources seen:", srcs, "(if only 'rules-fallback', your key/model/base URL is wrong)")
    S = write_report(runs)
    for n, s in S.items():
        print(f"{n:11s} total {pct(s['total'])}  intent {pct(s['intent'])}  facts {pct(s['facts'])}")
    print("Wrote TESTING.md and eval/results.json")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        i = sys.argv.index("--worker")
        worker(sys.argv[i + 1], "--llm" in sys.argv, float(sys.argv[sys.argv.index("--pause") + 1]))
    else:
        main()
