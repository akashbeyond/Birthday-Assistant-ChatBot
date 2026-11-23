"""V2 query service: validated {intent, entities} + DataFrame -> answer. No language parsing here."""
from __future__ import annotations
import calendar
from datetime import date, timedelta

HELP = ("Try questions such as:\n• What are the upcoming birthdays?\n• How many birthdays are there next month?\n"
        "• Is there any birthday tomorrow?\n• When is my wife's birthday?\n• Any nephew birthdays in September?\n"
        "• Who has birthdays this week?\n• When is Rahul Patil's birthday?\n• How old is Rahul Patil?\n"
        "• Who stays in Bengaluru?")


def _anniv(dob, year):
    try:
        return date(year, dob.month, dob.day)
    except ValueError:  # 29 Feb in a non-leap year
        return date(year, 2, 28)


def next_birthday(dob, today):
    c = _anniv(dob, today.year)
    return c if c >= today else _anniv(dob, today.year + 1)


def _fmt(rows, today):
    lines = []
    for _, r in rows.iterrows():
        dob = r["DOB"].date()
        d = (next_birthday(dob, today) - today).days
        when = "today" if d == 0 else "tomorrow" if d == 1 else f"in {d} days"
        lines.append(f"• {r['Name']} — {dob.strftime('%d %B')} ({r['Relationship']}; {when})")
    return "\n".join(lines)


def _sort_next(rows, today):
    if rows.empty:
        return rows
    key = rows["DOB"].apply(lambda x: next_birthday(x.date(), today))
    return rows.assign(_k=key).sort_values(["_k", "Name"]).drop(columns="_k")


def _window(e, today):
    rd = e.get("relative_date")
    if rd == "today": return today, today, "today"
    if rd == "tomorrow": return today + timedelta(1), today + timedelta(1), "tomorrow"
    if rd == "day_after_tomorrow": return today + timedelta(2), today + timedelta(2), "on the day after tomorrow"
    if rd == "this_week": return today, today + timedelta(6 - today.weekday()), "in the rest of this week"
    if rd == "next_week":
        s = today + timedelta(7 - today.weekday())
        return s, s + timedelta(6), "next week"
    if "within_days" in e:
        return today, today + timedelta(e["within_days"]), f"in the next {e['within_days']} days"
    return None


def _month(e, today):
    if e.get("relative_month") == "next": return (today.month % 12) + 1
    if e.get("relative_month") == "this": return today.month
    return e.get("month")


def _people(e, df):
    """Rows for the named person(s), narrowed by relationship if both were given."""
    if "person_id" in e:
        rows = df[df["Person_ID"] == e["person_id"]]
    else:
        rows = df[df["Person_ID"].isin(e.get("person_candidates", []))]
    if "relationship" in e:
        rows = rows[rows["Relationship"] == e["relationship"]]
    return rows


def _reply(answer, status="ok", rows=None):
    return {"answer": answer, "status": status, "result_ids": [] if rows is None else list(rows["Person_ID"])}


def _ambiguous(rows):
    names = "\n".join(f"• {r['Name']} ({r['Relationship']}, {r['Place_of_Stay']})" for _, r in rows.iterrows())
    return _reply(f"I found {len(rows)} matching people:\n{names}\nPlease use a full name.", "ambiguous", rows)


def execute(parsed, df, today: date | None = None) -> dict:
    today = today or date.today()
    intent, e = parsed["intent"], parsed["entities"]

    if intent == "help":
        return _reply(HELP, "help")
    if intent == "unknown":
        return _reply("I could not understand that. Type 'examples' to see what I can answer.", "unsupported")

    # ---- named person ---------------------------------------------------
    if "person_id" in e or "person_candidates" in e:
        rows = _people(e, df)
        if rows.empty:
            return _reply("I could not find anyone matching that in your list.", "empty")
        if len(rows) > 1:
            return _ambiguous(rows)
        r = rows.iloc[0]
        if intent == "person_place":
            return _reply(f"{r['Name']} stays in {r['Place_of_Stay']}.", "ok", rows)
        if intent == "person_age":
            dob = r["DOB"]
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return _reply(f"{r['Name']} is {age} years old as of {today.strftime('%d %B %Y')}.", "ok", rows)
        return _reply(f"{r['Name']}'s birthday is {r['DOB'].strftime('%d %B %Y')}.", "ok", rows)

    # ---- place listing --------------------------------------------------
    work = df
    if "relationship" in e:
        work = work[work["Relationship"] == e["relationship"]]
    if "place" in e:
        work = work[work["Place_of_Stay"] == e["place"]]
    if intent == "place_search":
        if work.empty:
            return _reply("No matching people found.", "empty")
        names = "\n".join(f"• {r['Name']} ({r['Relationship']})" for _, r in work.iterrows())
        return _reply(f"People staying in {e['place']}:\n{names}", "ok", work)

    # ---- date filters ---------------------------------------------------
    label = ""
    month = _month(e, today)
    if "day" in e:
        if e["day"] < 1 or e["day"] > calendar.monthrange(2000, month)[1]:
            return _reply(f"{calendar.month_name[month]} does not have a day {e['day']}.", "invalid")
        work = work[(work["DOB"].dt.month == month) & (work["DOB"].dt.day == e["day"])]
        label = f"on {e['day']} {calendar.month_name[month]}"
    elif month:
        work = work[work["DOB"].dt.month == month]
        label = f"in {calendar.month_name[month]}"
    else:
        win = _window(e, today)
        if win:
            s, t, label = win
            work = work[work["DOB"].apply(lambda x: next_birthday(x.date(), s) <= t)]
    who = (e["relationship"].lower() + " ") if "relationship" in e else ""
    where = f" staying in {e['place']}" if "place" in e else ""

    # "my wife" -> the record marked Spouse (the sheet has a second 'Wife' row without that detail)
    if e.get("relationship") == "Wife" and not month and not _window(e, today):
        sp = work[work["Relationship_Detail"].str.casefold() == "spouse"]
        work = sp if not sp.empty else work

    if intent == "count_birthdays":
        n = len(work)
        verb, noun = ("is", "birthday") if n == 1 else ("are", "birthdays")
        return _reply(f"There {verb} {n} {who}{noun}{where} {label}".strip() + ".", "ok", work)

    if work.empty:
        return _reply(f"No {who}birthdays found{where} {label}".strip() + ".", "empty")
    if month and "day" not in e:
        work = work.assign(_d=work["DOB"].dt.day).sort_values(["_d", "Name"]).drop(columns="_d")
    else:
        work = _sort_next(work, today)
    head = f"{(who + 'birthdays').capitalize()}{where} {label}".strip()
    if not label and len(work) == 1:
        r = work.iloc[0]
        return _reply(f"{r['Name']}'s birthday is {r['DOB'].strftime('%d %B %Y')} ({r['Relationship']}).", "ok", work)
    return _reply(f"{head}:\n{_fmt(work, today)}", "ok", work)
