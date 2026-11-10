#!/usr/bin/env python3
"""Uppdaterar F1-raderna i events.json från Jolpica F1 API (gratis, ingen nyckel).

Körs av GitHub Actions varje vecka. Rör bara tävlingar med sporten "mot" (F1)
som ännu inte har körts. Allt annat i events.json lämnas orört.
"""
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://api.jolpi.ca/ergast/f1/{}.json?limit=100"
FILE = Path(__file__).resolve().parent.parent / "events.json"
TODAY = dt.date.today()

# Jolpicas loppnamn -> svenska namn (samma som redan finns i events.json)
SV = {
    "Australian": "Australien", "Chinese": "Kina", "Japanese": "Japan",
    "Bahrain": "Bahrain", "Saudi Arabian": "Saudiarabien", "Miami": "Miami",
    "Emilia Romagna": "Emilia-Romagna", "Monaco": "Monaco", "Canadian": "Kanada",
    "Spanish": "Spanien", "Madrid": "Spanien", "Austrian": "Österrike",
    "British": "Storbritannien", "Hungarian": "Ungern", "Belgian": "Belgien",
    "Dutch": "Nederländerna", "Italian": "Italien", "Azerbaijan": "Azerbajdzjan",
    "Singapore": "Singapore", "United States": "USA", "Mexico City": "Mexiko",
    "Mexican": "Mexiko", "São Paulo": "Brasilien", "Brazilian": "Brasilien",
    "Las Vegas": "Las Vegas", "Qatar": "Qatar", "Abu Dhabi": "Abu Dhabi",
    "Portuguese": "Portugal", "Turkish": "Turkiet", "Malaysian": "Malaysia",
}


def fetch(season):
    req = urllib.request.Request(
        URL.format(season), headers={"User-Agent": "nextcup-calendar/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["MRData"]["RaceTable"]["Races"]


def strip(name):
    return name.replace(" (sprint)", "")


def build(race, old):
    base = race["raceName"].replace(" Grand Prix", "")
    name = "F1: " + SV.get(base, base) + (" (sprint)" if "Sprint" in race else "")
    race_d = dt.date.fromisoformat(race["date"])
    quali = (race.get("Qualifying") or {}).get("date") or (
        race_d - dt.timedelta(days=1)
    ).isoformat()
    prev = old.get(strip(name))
    ev = {
        "s": quali,
        "e": race["date"],
        "n": name,
        "k": "mot",
        "p": prev["p"] if prev else race["Circuit"]["Location"]["locality"],
        "tv": "Viaplay",
    }
    if prev and prev.get("d"):
        ev["d"] = prev["d"]
    return ev


def save(data):
    events = sorted(data["events"], key=lambda o: (o["s"], o["e"]))
    rows = ",\n".join(json.dumps(o, ensure_ascii=False) for o in events)
    FILE.write_text(
        '{\n"updated":%s,\n"sports":%s,\n"events":[\n%s\n]\n}\n'
        % (
            json.dumps(data["updated"]),
            json.dumps(data["sports"], ensure_ascii=False),
            rows,
        ),
        encoding="utf-8",
    )


def main():
    data = json.loads(FILE.read_text(encoding="utf-8"))
    old_events = data["events"]
    old = {strip(o["n"]): o for o in old_events if o["k"] == "mot"}
    fresh, seasons_ok, errors = [], [], 0
    for season in (TODAY.year, TODAY.year + 1):
        try:
            races = fetch(season)
        except Exception as e:  # nätverksfel, API nere osv.
            print(f"Varning: kunde inte hämta {season}: {e}")
            errors += 1
            continue
        if not races:
            print(f"{season}: ingen kalender publicerad än, hoppar över")
            continue
        seasons_ok.append(season)
        for r in races:
            if dt.date.fromisoformat(r["date"]) >= TODAY:
                fresh.append(build(r, old))
    if errors == 2:
        sys.exit("Båda hämtningarna misslyckades, ändrar ingenting.")

    keep = [
        o for o in old_events
        if not (o["k"] == "mot" and int(o["e"][:4]) in seasons_ok and o["e"] >= TODAY.isoformat())
    ]
    new_events = keep + fresh
    key = lambda L: sorted(json.dumps(o, ensure_ascii=False, sort_keys=True) for o in L)
    if key(new_events) == key(old_events):
        print("Inga ändringar i F1-kalendern.")
        return
    before = {(o["n"], o["e"][:4]): o for o in old_events if o["k"] == "mot"}
    after = {(o["n"], o["e"][:4]): o for o in fresh}
    for n in sorted(after.keys() - before.keys()):
        print("Ny:", n[0], after[n]["s"], "-", after[n]["e"])
    for n in sorted(before.keys() - after.keys()):
        if before[n]["e"] >= TODAY.isoformat() and int(before[n]["e"][:4]) in seasons_ok:
            print("Borttagen:", n[0], n[1])
    for n in sorted(before.keys() & after.keys()):
        if (before[n]["s"], before[n]["e"]) != (after[n]["s"], after[n]["e"]):
            print("Ändrad:", n[0], before[n]["s"], before[n]["e"], "->", after[n]["s"], after[n]["e"])
    data["events"] = new_events
    data["updated"] = TODAY.isoformat()
    save(data)


if __name__ == "__main__":
    main()
