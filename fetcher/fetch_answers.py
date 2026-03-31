#!/usr/bin/env python3
"""
CodyCross Answer Fetcher v4.0
================================
Fetches ALL world puzzle data from the CodyCross PRODUCTION API.
Uses appVersion=1.0.0 which returns COMPLETELY UNENCRYPTED puzzle data.

Data Source: CodyCross Production API (game.codycross-game.com)
Endpoint:   /Puzzle/GetMundo?mundo=N&...&appVersion=1.0.0

Response format:
  Records[0] = World metadata (Nome, GruposDeFases with puzzle UUIDs)
  Records[1] = Array of puzzle items (Id, Resposta, Cifras[{Dica, Resposta}])

Usage:
    python3 fetch_answers.py              # Fetch worlds 1-5 (quick test)
    python3 fetch_answers.py --max 10     # Fetch worlds 1-10
    python3 fetch_answers.py --all        # Fetch ALL worlds (1-200+)
    python3 fetch_answers.py --start 6    # Start from world 6
    python3 fetch_answers.py --workers 4  # Parallel fetch with 4 workers
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIGURATION
# ============================================================

API_BASE = "https://game.codycross-game.com"
TOKEN = "872fbb4c-fa3c-4534-b6e4-4b56bd7d3fc6"
LANG = "1aca585a-8e15-3029-89a0-54aa078acec2"  # English
COUNTRY = "US"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ANSWERS_FILE = os.path.join(DATA_DIR, "answers.json")

# How many worlds to try before giving up (incrementally)
MAX_WORLD_PROBE = 200

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
REQUEST_TIMEOUT = 30  # seconds
PARALLEL_WORKERS = 4  # default parallel workers

# ============================================================
# API COMMUNICATION
# ============================================================

def api_get(mundo_num, retries=MAX_RETRIES):
    """Fetch world data from the production API with retries."""
    params = {
        "mundo": str(mundo_num),
        "country": COUNTRY,
        "dificuldadeDoPuzzle": "2",
        "androidLang": "en",
        "deviceType": "Android",
        "appVersion": "1.0.0",
    }
    url = f"{API_BASE}/Puzzle/GetMundo?" + "&".join(f"{k}={v}" for k, v in params.items())

    headers = {
        "User-Agent": "CodyCross/1.0.0 (Android 12; SDK 31)",
        "Accept": "application/json",
    }

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # World doesn't exist
            print(f"    [!] World {mundo_num}: HTTP {e.code} (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(RETRY_DELAY * attempt)
        except urllib.error.URLError as e:
            print(f"    [!] World {mundo_num}: Network error (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(RETRY_DELAY * attempt)
        except json.JSONDecodeError as e:
            print(f"    [!] World {mundo_num}: JSON error (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(RETRY_DELAY * attempt)
        except Exception as e:
            print(f"    [!] World {mundo_num}: Unexpected error: {e}")
            if attempt < retries:
                time.sleep(RETRY_DELAY * attempt)

    return None  # All retries exhausted


# ============================================================
# DATA PROCESSING
# ============================================================

def parse_world(raw_data, mundo_num):
    """
    Parse raw API response into our answer format.

    Raw response:
      Records[0] = { Nome, Numero, GruposDeFases: [{ Numero, Fases: [{ Puzzle, Indice }] }] }
      Records[1] = [{ Id, Resposta, Cifras: [{ Dica, Resposta }] }]

    Output:
      {
        "world": 1,
        "worldName": "Earth",
        "groups": [
          {
            "groupNumber": 1,
            "groupName": "...", (if available)
            "puzzles": [
              { "clue": "...", "answer": "..." },
              ...
            ]
          }
        ],
        "stats": { "groups": N, "puzzles": N, "clues": N }
      }
    """
    if not raw_data or not raw_data.get("Ok"):
        return None

    records = raw_data.get("Records", [])
    if len(records) < 2:
        return None

    world_meta = records[0]
    puzzle_items = records[1]

    if not isinstance(puzzle_items, list):
        return None

    world_name = world_meta.get("Nome", world_meta.get("Name", f"World {mundo_num}"))
    world_number = world_meta.get("Numero", mundo_num)
    grupos = world_meta.get("GruposDeFases", [])

    # Build a lookup: puzzle_id -> puzzle_data
    puzzle_lookup = {}
    for item in puzzle_items:
        pid = item.get("Id")
        if pid:
            puzzle_lookup[pid] = item

    # Build groups
    groups = []
    total_clues = 0
    total_puzzles = 0

    for grupo in grupos:
        group_number = grupo.get("Numero", 0)
        fases = grupo.get("Fases", [])

        all_puzzles = []

        for fase in fases:
            puzzle_id = fase.get("Puzzle")
            puzzle_data = puzzle_lookup.get(puzzle_id)

            if not puzzle_data:
                continue

            # Add the main answer as a clue/answer pair (the primary puzzle answer)
            main_answer = puzzle_data.get("Resposta", "")
            if main_answer:
                # Find the primary clue from Cifras (the one that corresponds to the main answer)
                cifras = puzzle_data.get("Cifras", [])
                primary_clue = None
                for c in cifras:
                    if c.get("Resposta", "").lower() == main_answer.lower():
                        primary_clue = c.get("Dica", "")
                        break

                # Add main puzzle answer
                if primary_clue and main_answer:
                    all_puzzles.append({
                        "clue": primary_clue,
                        "answer": main_answer,
                        "isMain": True,
                    })

                # Also add all individual clues from Cifras
                for cifra in cifras:
                    clue_text = cifra.get("Dica", "")
                    clue_answer = cifra.get("Resposta", "")
                    if clue_text and clue_answer:
                        # Avoid duplicate if this is the main answer clue
                        if clue_answer.lower() != main_answer.lower():
                            all_puzzles.append({
                                "clue": clue_text,
                                "answer": clue_answer,
                                "isMain": False,
                            })

        total_puzzles += len(fases)
        total_clues += len(all_puzzles)

        if all_puzzles:
            groups.append({
                "groupNumber": group_number,
                "puzzles": all_puzzles,
            })

    if not groups:
        return None

    return {
        "world": world_number,
        "worldName": world_name,
        "groups": groups,
        "stats": {
            "groups": len(groups),
            "puzzles": total_puzzles,
            "clues": total_clues,
        },
    }


def detect_max_world(workers=2):
    """Probe the API to find the maximum world number."""
    print("[*] Detecting maximum world number...")
    max_found = 0

    # Check in batches
    batch_size = 20
    for start in range(1, MAX_WORLD_PROBE + 1, batch_size):
        batch = list(range(start, start + batch_size))
        found_in_batch = False

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(api_get, n, retries=1): n for n in batch}
            for future in as_completed(futures):
                n = futures[future]
                try:
                    data = future.result()
                    if data and data.get("Ok"):
                        max_found = max(max_found, n)
                        found_in_batch = True
                except:
                    pass

        if not found_in_batch and max_found > 0 and start > max_found + 5:
            # If we haven't found anything in a while past the max, stop probing
            break

        # Small delay between batches
        time.sleep(0.3)

    return max_found


# ============================================================
# FILE MANAGEMENT
# ============================================================

def load_existing_answers():
    """Load existing answers.json for incremental updates."""
    if os.path.exists(ANSWERS_FILE):
        try:
            with open(ANSWERS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_answers(data):
    """Save the complete answers data to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Update site metadata
    data["site"] = {
        "name": "CodyCross Answers",
        "description": "Complete CodyCross puzzle answers — all worlds, all groups, all clues",
        "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
        "dataSource": "CodyCross Production API (game.codycross-game.com/Puzzle/GetMundo)",
        "apiParams": "appVersion=1.0.0 (unencrypted endpoint)",
        "totalWorlds": len(data.get("answers", [])),
        "totalClues": sum(
            w.get("stats", {}).get("clues", 0)
            for w in data.get("answers", [])
        ) if data.get("answers") else 0,
        "updateMethod": "GitHub Actions + manual fetch",
    }

    with open(ANSWERS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  [+] Saved to {ANSWERS_FILE}")
    print(f"  [+] Worlds: {data['site']['totalWorlds']}, Total clues: {data['site']['totalClues']}")


# ============================================================
# MAIN FETCHER
# ============================================================

def fetch_worlds(start=1, end=5, workers=PARALLEL_WORKERS):
    """Fetch a range of worlds with parallel requests."""
    results = []
    failed = []

    print(f"\n[*] Fetching worlds {start} to {end} with {workers} parallel workers...")
    world_nums = list(range(start, end + 1))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(api_get, n): n for n in world_nums}

        for future in as_completed(futures):
            n = futures[future]
            try:
                raw = future.result()
                if raw and raw.get("Ok"):
                    parsed = parse_world(raw, n)
                    if parsed:
                        results.append(parsed)
                        stats = parsed["stats"]
                        print(f"  [+] World {n}: \"{parsed['worldName']}\" — {stats['groups']} groups, {stats['clues']} clues")
                    else:
                        print(f"  [-] World {n}: No puzzle data (empty)")
                        failed.append(n)
                else:
                    print(f"  [-] World {n}: Not found or error")
                    failed.append(n)
            except Exception as e:
                print(f"  [!] World {n}: Exception: {e}")
                failed.append(n)

    # Sort by world number
    results.sort(key=lambda x: x["world"])

    return results, failed


def main():
    print("=" * 60)
    print("  CodyCross Answer Fetcher v4.0")
    print("  Endpoint: Puzzle/GetMundo (production, unencrypted)")
    print("=" * 60)

    # Parse arguments
    fetch_all = False
    max_worlds = 5
    start_world = 1
    workers = PARALLEL_WORKERS

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--all":
            fetch_all = True
        elif arg == "--max" and i + 1 < len(args):
            max_worlds = int(args[i + 1])
            i += 1
        elif arg == "--start" and i + 1 < len(args):
            start_world = int(args[i + 1])
            i += 1
        elif arg == "--workers" and i + 1 < len(args):
            workers = int(args[i + 1])
            i += 1
        elif arg == "--demo":
            run_demo_mode()
            return 0
        i += 1

    if fetch_all:
        # First detect the max world number
        max_world_num = detect_max_world(workers=2)
        if max_world_num < start_world:
            print(f"[!] No worlds found starting from {start_world}")
            return 1
        end_world = max_world_num
        print(f"  [+] Detected {max_world_num} total worlds")
    else:
        end_world = max_worlds

    if end_world < start_world:
        print(f"[!] Invalid range: start={start_world}, end={end_world}")
        return 1

    # Load existing data for incremental update
    existing = load_existing_answers()
    existing_world_map = {}
    if existing and existing.get("answers"):
        for w in existing["answers"]:
            existing_world_map[w["world"]] = w

    # Fetch worlds
    results, failed = fetch_worlds(start=start_world, end=end_world, workers=workers)

    if not results:
        print("\n[!] No world data fetched successfully!")
        return 1

    # Merge with existing data
    if existing_world_map:
        for r in results:
            existing_world_map[r["world"]] = r
        # Also keep worlds that were in existing but not re-fetched
        all_worlds = sorted(existing_world_map.values(), key=lambda x: x["world"])
    else:
        all_worlds = results

    # Build final output
    output = {
        "site": {},  # Filled by save_answers
        "answers": all_worlds,
    }

    # Save
    save_answers(output)

    # Summary
    total_clues = sum(w["stats"]["clues"] for w in results)
    total_groups = sum(w["stats"]["groups"] for w in results)
    print(f"\n{'=' * 60}")
    print(f"  Done! Fetched {len(results)} worlds")
    print(f"  Total: {total_groups} groups, {total_clues} clues")
    if failed:
        print(f"  Failed/skipped: {len(failed)} worlds")
    print(f"{'=' * 60}")

    return 0


def run_demo_mode():
    """Generate demo data for testing the frontend."""
    worlds = [
        {
            "world": 1,
            "worldName": "Earth",
            "groups": [
                {
                    "groupNumber": 1,
                    "puzzles": [
                        {"clue": "One hundred times ten is equal to one __", "answer": "thousand"},
                        {"clue": "Parts of a TV show that make up a series", "answer": "episodes"},
                        {"clue": "Type of network that does not need cables", "answer": "wireless"},
                        {"clue": "Ocular covering worn by a pirate", "answer": "eyepatch"},
                        {"clue": "Bread-making shops", "answer": "bakeries"},
                    ]
                },
                {
                    "groupNumber": 2,
                    "puzzles": [
                        {"clue": "Clark Kent's hero name", "answer": "superman"},
                        {"clue": "Sincere and emotional, from the cardiac organ", "answer": "heartfelt"},
                        {"clue": "Member of the press who conducts interviews", "answer": "reporter"},
                        {"clue": "Compelling attractiveness; charm", "answer": "charisma"},
                    ]
                }
            ],
            "stats": {"groups": 2, "puzzles": 10, "clues": 9}
        },
        {
            "world": 2,
            "worldName": "Under the Sea",
            "groups": [
                {
                    "groupNumber": 1,
                    "puzzles": [
                        {"clue": "Largest mammal in the ocean", "answer": "blue whale"},
                        {"clue": "Clownfish's home in the movie Finding Nemo", "answer": "anemone"},
                        {"clue": "Crustacean with pincers", "answer": "crab"},
                    ]
                }
            ],
            "stats": {"groups": 1, "puzzles": 5, "clues": 3}
        }
    ]

    output = {"site": {}, "answers": worlds}
    save_answers(output)
    print("[+] Demo mode complete")


if __name__ == "__main__":
    sys.exit(main())
