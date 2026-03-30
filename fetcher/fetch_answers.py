#!/usr/bin/env python3
"""
CodyCross Daily Answer Fetcher v3.0
========================================
Fetches today's crossword puzzle data from the CodyCross API.
Uses the unencrypted Crossword/TodaysCrossword endpoint — no AES key needed!

Data Source: CodyCross Dev API (codydev.fulano.com.br)
Endpoint:   /Crossword/TodaysCrossword (unencrypted)

Usage:
    python3 fetcher.py                   # Fetch today's crossword
    python3 fetch_answers.py --demo        # Generate demo data
    python3 fetch_answers.py --all-worlds  # Also fetch world metadata
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ============================================================
# CONFIGURATION
# ============================================================

API_BASE = "https://codydev.fulano.com.br"
TOKEN = "872fbb4c-fa3c-4534-b6e4-4bbb-4b56bd7d3fc6"
LANG = "1aca585a-8e15-3029-89a0-54aa078acec2"  # English
COUNTRY = "US"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ANSWERS_FILE = os.path.join(DATA_DIR, "answers.json")


# ============================================================
# API COMMUNICATION
# ============================================================

def api_get(path, extra_params=None):
    """Make GET request to CodyCross API."""
    url = f"{API_BASE}{path}"
    if extra_params:
        url += "&" + "&".join(f"{k}={v}" for k, v in extra_params.items())

    headers = {
        "User-Agent": "CodyCross/1.0.0 (Android 12; SDK 31)",
        "Accept": "application/json",
        "Accept-Language": "en-US",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"  Network error: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None


# ============================================================
# DATA FETCHING
# ============================================================

def fetch_todays_crossword():
    """Fetch today's crossword from the unencrypted endpoint."""
    params = {
        "token": TOKEN,
        "lang": LANG,
    }
    path = f"/Crossword/TodaysCrossword?token={TOKEN}&lang={LANG}"
    return api_get(path)


def fetch_world_metadata(mundo_num):
    """Fetch world structure (group/puzzle IDs) — unencrypted with old app version."""
    params = {
        "token": TOKEN,
        "lang": LANG,
        "mundo": str(mundo_num),
        "country": COUNTRY,
        "dificuldadeDoPuzzle": "2",
        "androidLang": "en",
        "deviceType": "Android",
        "appVersion": "1.0.0",
    }
    path = "/Puzzle/GetMundo?" + "&".join(f"{k}={v}" for k, v in params.items())
    return api_get(path)


def fetch_game_texts():
    """Fetch localization/UI text strings (always unencrypted)."""
    path = "/Texto/List?androidLang=en&deviceType=Android&appVersion=1.0.0"
    return api_get(path)


# ============================================================
# DATA PROCESSING
# ============================================================

def parse_crossword_data(raw):
    """
    Parse the Crossword/TodaysCrossword response into our answer format.

    The response looks like:
    {
      "Records": [{
        "TodaysPuzzles": [{
          "Id": "...",
          "GroupName": "...",
          "CrosswordData": { ... },
          "Clues": [ { "Question": "...", "Answer": "..." } ],
          ...
        }],
        "TimeUntilExpiration": "...",
        "Year": 2026,
        "Month": 3
      }]
    }
    """
    if not raw or not raw.get("Ok"):
        return None

    records = raw.get("Records", [])
    if not records:
        return None

    record = records[0]
    today_puzzles = record.get("TodaysPuzzles", [])
    year = record.get("Year", datetime.now().year)
    month = record.get("Month", datetime.now().month)

    if not today_puzzles:
        return None

    groups = []
    theme = f"CodyCross Daily Crossword — {year}"

    for puzzle in today_puzzles:
        group_name = puzzle.get("GroupName", puzzle.get("Name", f"Puzzle"))

        # Extract clues/answers from the puzzle data
        clues = puzzle.get("Clues", [])
        if not clues:
            # Try nested structures
            crossword_data = puzzle.get("CrosswordData", {})
            if crossword_data:
                clues = crossword_data.get("Clues", [])

        puzzles = []
        if clues:
            for clue in clues:
                question = clue.get("Question", clue.get("Clue", clue.get("Text", "")))
                answer = clue.get("Answer", clue.get("Solution", clue.get("Word", "")))
                if question and answer:
                    puzzles.append({
                        "clue": question,
                        "answer": answer
                    })

        # If no clues found, try to extract from the raw puzzle structure
        if not puzzles:
            # Try various field names that might contain clue/answer data
            for key, val in puzzle.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            q = item.get("Question", item.get("Clue", item.get("Text", "")))
                            a = item.get("Answer", item.get("Solution", item.get("Word", "")))
                            if q and a and len(a) > 1:
                                puzzles.append({"clue": q, "answer": a})

        if puzzles:
            groups.append({
                "name": group_name,
                "puzzles": puzzles
            })

    return {
        "theme": theme,
        "groups": groups,
        "year": year,
        "month": month
    } if groups else None


def parse_world_metadata(raw):
    """Parse world metadata into a summary format for the archive."""
    if not raw or not raw.get("Ok"):
        return None

    worlds = []
    records = raw.get("Records", [])
    for record in records:
        if isinstance(record, dict):
            nome = record.get("Nome", record.get("Name", ""))
            numero = record.get("Numero", record.get("Number", 0))
            grupos = record.get("GruposDeFases", [])
            total_puzzles = 0
            for g in grupos:
                fases = g.get("Fases", [])
                total_puzzles += len(fases)
            worlds.append({
                "name": nome,
                "number": numero,
                "groups": len(grupos),
                "puzzles": total_puzzles,
            })
    return worlds


# ============================================================
# ANSWERS FILE MANAGEMENT
# ============================================================

def load_answers():
    """Load existing answers.json."""
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, "r") as f:
            return json.load(f)
    return {
        "site": {
            "name": "CodeCross Daily Answers",
            "description": "Daily crossword answers fetched from CodyCross API",
            "lastUpdated": datetime.now().strftime("%Y-%m-%d"),
            "dataSource": "CodyCross API (codydev.fulano.com.br/Crossword/TodaysCrossword)",
            "apiEndpoint": API_BASE,
            "updateMethod": "GitHub Actions (automated daily fetch, no encryption needed)"
        },
        "answers": []
    }


def save_answer_entry(entry):
    """Add/update an answer entry in answers.json."""
    data = load_answers()

    today_str = entry["date"]

    # Remove existing entry for same date
    data["answers"] = [a for a in data.get("answers", []) if a.get("date") != today_str]

    # Add new entry at the beginning
    data["answers"].insert(0, entry)
    data["site"]["lastUpdated"] = today_str

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ANSWERS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    group_count = len(entry.get("groups", []))
    puzzle_count = sum(len(g.get("puzzles", [])) for g in entry.get("groups", []))
    print(f"  [+] Updated {ANSWERS_FILE}")
    print(f"  [+] Date: {today_str}, Theme: {entry.get('theme', 'N/A')}")
    print(f"  [+] Groups: {group_count}, Total clues: {puzzle_count}")


# ============================================================
# MAIN
# ============================================================

def run_demo_mode():
    """Generate realistic demo data."""
    today_str = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "date": today_str,
        "theme": "CodyCross Daily Crossword",
        "year": datetime.now().year,
        "month": datetime.now().month,
        "groups": [
            {
                "name": "Morning Puzzles",
                "puzzles": [
                    {"clue": "A large body of salt water", "answer": "OCEAN"},
                    {"clue": "The color of grass", "answer": "GREEN"},
                    {"clue": "A domesticated feline pet", "answer": "CAT"},
                    {"clue": "The star at the center of our solar system", "answer": "SUN"},
                    {"clue": "Frozen water falls as this", "answer": "SNOW"},
                ]
            },
            {
                "name": "Afternoon Challenges",
                "puzzles": [
                    {"clue": "A device used to tell time", "answer": "CLOCK"},
                    {"clue": "The opposite of hot", "answer": "COLD"},
                    {"clue": "A musical instrument with strings", "answer": "GUITAR"},
                    {"clue": "The planet we live on", "answer": "EARTH"},
                ]
            }
        ]
    }

    save_answer_entry(entry)
    return True


def main():
    print("=" * 60)
    print("  CodyCross Daily Answer Fetcher v3.0")
    print("  Endpoint: Crossword/TodaysCrossword (unencrypted)")
    print("=" * 60)

    # Parse arguments
    demo = False
    for arg in sys.argv[1:]:
        if arg == "--demo":
            demo = True

    if demo:
        print("\n[*] Running in DEMO mode")
        return run_demo_mode()

    # Step 1: Fetch today's crossword
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[*] Fetching today's crossword ({today_str})...")

    raw = fetch_todays_crossword()

    if not raw:
        print("  [!] Failed to fetch crossword data")
        # Try anyway with placeholder
        entry = {
            "date": today_str,
            "theme": "CodyCross Daily Crossword",
            "year": datetime.now().year,
            "month": datetime.now().month,
            "groups": []
        }
        save_answer_entry(entry)
        return 1

    print(f"  [+] API responded: Ok={raw.get('Ok')}")
    records = raw.get("Records", [])
    if records:
        expiry = records[0].get("TimeUntilExpiration", "N/A")
        year = records[0].get("Year", "?")
        month = records[0].get("Month", "?")
        puzzles = records[0].get("TodaysPuzzles", [])
        print(f"  [+] Year: {year}, Month: {month}, Expiry: {expiry}")
        print(f"  [+] Today's puzzles: {len(puzzles)}")

    # Step 2: Parse and save
    parsed = parse_crossword_data(raw)

    if parsed and parsed.get("groups"):
        entry = {
            "date": today_str,
            "theme": parsed["theme"],
            "year": parsed.get("year", datetime.now().year),
            "month": parsed.get("month", datetime.now().month),
            "groups": parsed["groups"]
        }
        save_answer_entry(entry)
        return 0
    else:
        print("  [!] No puzzle data found (puzzles may not be available yet)")
        print("  [!] This is normal if run before the daily puzzle releases")
        print("  [!] The daily puzzle refreshes around 05:00 UTC")

        entry = {
            "date": today_str,
            "theme": "CodyCross Daily Crossword",
            "year": datetime.now().year,
            "month": datetime.now().month,
            "groups": []
        }
        save_answer_entry(entry)
        return 1

    # Step 3: Also fetch game texts
    print(f"\n[*] Fetching game text strings...")
    text_data = fetch_game_texts()
    if text_data and text_data.get("Ok"):
        text_records = text_data.get("Records", [])
        texts = {}
        for rec in text_records:
            ident = rec.get("Identificador", "")
            valor = rec.get("Valor", {})
            if isinstance(valor, dict) and "en" in valor:
                texts[ident] = valor["en"]

        os.makedirs(DATA_DIR, exist_ok=True)
        texts_path = os.path.join(DATA_DIR, "game_texts.json")
        with open(texts_path, "w") as f:
            json.dump(texts, f, indent=2, ensure_ascii=False)
        print(f"  [+] Saved {len(texts)} text entries")

    print(f"\n{'=' * 60}")
    print(f"  Done! Check {DATA_DIR}/ for output files.")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
