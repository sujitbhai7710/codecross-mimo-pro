#!/usr/bin/env python3
"""
CodyCross Daily Answer Fetcher
===============================
Automatically fetches puzzle data from the CodyCross API,
decrypts it using the AES-256 key, and updates the website data files.

Data Source: CodyCross API (codydev.fulano.com.br, game.codycross-game.com)
Encryption: AES-256-CBC (key extracted via Frida from app binary)

Usage:
    python3 fetch_answers.py                    # Fetch today's answers (needs GAME_AES_KEY env)
    python3 fetch_answers.py --mundo 1          # Fetch specific world
    python3 fetch_answers.py --demo             # Demo mode with sample data
    GAME_AES_KEY=<hex> python3 fetch_answers.py # With explicit key

Environment Variables:
    GAME_AES_KEY  - Hex-encoded AES-256 key (32 bytes = 64 hex chars)
"""

import json
import base64
import hashlib
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ============================================================
# CONFIGURATION
# ============================================================

# Dev API (still active)
DEV_API_BASE = "https://codydev.fulano.com.br"
# Production API
PROD_API_BASE = "https://game.codycross-game.com"

TOKEN = "872fbb4c-fa3c-4534-b6e4-4b56bd7d3fc6"
LANG = "1aca585a-8e15-3029-89a0-54aa078acec2"  # English
COUNTRY = "US"
DEVICE_TYPE = "Android"
APP_VERSION = "1.31.0"
DIFFICULTY = 2  # Normal difficulty

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ANSWERS_FILE = os.path.join(DATA_DIR, "answers.json")

def get_aes_key():
    """Get the AES key from environment variable."""
    key_hex = os.environ.get("GAME_AES_KEY", "")
    if not key_hex:
        return None
    # Clean the key (remove spaces, ensure lowercase)
    key_hex = key_hex.strip().lower().replace(" ", "")
    if len(key_hex) != 64:
        print(f"  [!] Invalid key length: {len(key_hex)} hex chars (expected 64)")
        return None
    try:
        return bytes.fromhex(key_hex)
    except ValueError:
        print(f"  [!] Invalid hex key")
        return None


# ============================================================
# API COMMUNICATION
# ============================================================

def api_get(url, extra_headers=None):
    """Make GET request to API and return parsed JSON."""
    headers = {
        "User-Agent": "CodyCross/2.8.1 (Android 12; SDK 31)",
        "Accept": "application/json",
        "Accept-Language": "en-US",
    }
    if extra_headers:
        headers.update(extra_headers)
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"  Network error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None


def fetch_text_list():
    """Fetch UI text/localization strings (unencrypted)."""
    url = f"{DEV_API_BASE}/Texto/List?androidLang=en&deviceType={DEVICE_TYPE}&appVersion={APP_VERSION}"
    return api_get(url)


def fetch_puzzle_world(mundo_num, api_base=None):
    """
    Fetch puzzle data for a specific world.
    Returns encrypted records that need AES-256-CBC decryption.
    """
    base = api_base or DEV_API_BASE
    params = {
        "token": TOKEN,
        "lang": LANG,
        "mundo": str(mundo_num),
        "country": COUNTRY,
        "dificuldadeDoPuzzle": str(DIFFICULTY),
        "androidLang": "en",
        "deviceType": DEVICE_TYPE,
        "appVersion": APP_VERSION,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{base}/Puzzle/GetMundo?{query}"
    print(f"  URL: {url}")
    return api_get(url)


def fetch_todays_crossword():
    """Try fetching today's crossword from production API."""
    # Today's crossword endpoint (needs auth token from player login)
    url = f"{PROD_API_BASE}/Crossword/TodaysCrossword?token={TOKEN}&lang={LANG}"
    return api_get(url)


def fetch_daily_puzzle():
    """Try DDR daily puzzle endpoint."""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{PROD_API_BASE}/DDR/Daily/Date({today})?token={TOKEN}&lang={LANG}"
    return api_get(url)


def login_device():
    """Login with a fake device to get an auth token."""
    login_data = json.dumps({
        "deviceId": "ci-" + hashlib.md5(os.urandom(16)).hexdigest()[:16],
        "deviceType": DEVICE_TYPE,
        "appVersion": APP_VERSION,
        "platform": "android",
        "country": COUNTRY,
        "language": LANG,
    }).encode()

    url = f"{PROD_API_BASE}/Player/login"
    try:
        req = urllib.request.Request(url, data=login_data, headers={
            "Content-Type": "application/json",
            "User-Agent": "CodyCross/2.8.1 (Android 12; SDK 31)",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  Login failed: {e}")
        return None


# ============================================================
# DECRYPTION
# ============================================================

def decrypt_aes_cbc(encrypted_bytes, key):
    """
    Decrypt AES-256-CBC data.
    Format: [16 bytes IV][ciphertext][PKCS7 padding]
    """
    try:
        from Crypto.Cipher import AES
    except ImportError:
        try:
            from Cryptodome.Cipher import AES
        except ImportError:
            print("  [!] pycryptodome not installed. Run: pip3 install pycryptodome")
            return None
    
    if len(encrypted_bytes) < 32:
        print(f"  [!] Data too short: {len(encrypted_bytes)} bytes")
        return None
    
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(ciphertext)
        
        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 16 and all(b == pad_len for b in decrypted[-pad_len:]):
            decrypted = decrypted[:-pad_len]
        
        return decrypted
    except Exception as e:
        print(f"  [!] Decryption error: {e}")
        return None


def try_decrypt_with_key(encrypted_b64, key):
    """Decrypt a base64-encoded encrypted record."""
    try:
        b64_clean = encrypted_b64.replace("\\u002B", "+")
        encrypted_bytes = base64.b64decode(b64_clean)
        decrypted = decrypt_aes_cbc(encrypted_bytes, key)
        
        if decrypted:
            try:
                text = decrypted.decode("utf-8")
                return text
            except UnicodeDecodeError:
                return None
        return None
    except Exception as e:
        print(f"  [!] Decrypt failed: {e}")
        return None


# ============================================================
# DATA PROCESSING
# ============================================================

def parse_decrypted_puzzle(json_str):
    """
    Parse decrypted puzzle data into our answer format.
    
    The exact structure depends on the decrypted JSON format.
    We try multiple known formats.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    
    groups = []
    theme = "Unknown"
    world = 1
    
    # Format 1: { "groups": [{ "name": "...", "puzzles": [{ "clue": "...", "answer": "..." }] }] }
    if "groups" in data:
        groups = []
        for g in data["groups"]:
            name = g.get("name", g.get("groupName", g.get("title", f"Group {len(groups)+1}")))
            puzzles = []
            for p in g.get("puzzles", g.get("questions", g.get("items", []))):
                clue = p.get("clue", p.get("question", p.get("text", p.get("definition", ""))))
                answer = p.get("answer", p.get("solution", p.get("word", p.get("value", ""))))
                if clue and answer:
                    puzzles.append({"clue": clue, "answer": answer})
            if puzzles:
                groups.append({"name": name, "puzzles": puzzles})
        theme = data.get("theme", data.get("worldName", data.get("title", "Unknown")))
        world = data.get("world", data.get("worldNumber", data.get("mundo", 1)))
    
    # Format 2: { "Records": [...] }  where each record has puzzle data
    elif "Records" in data:
        for rec in data["Records"]:
            if isinstance(rec, dict):
                # Recurse into each record
                result = parse_decrypted_puzzle(json.dumps(rec))
                if result and result["groups"]:
                    groups.extend(result["groups"])
    
    # Format 3: Array of puzzle items
    elif isinstance(data, list):
        puzzles = []
        for item in data:
            if isinstance(item, dict):
                clue = item.get("clue", item.get("question", item.get("definition", "")))
                answer = item.get("answer", item.get("solution", item.get("word", "")))
                group = item.get("group", item.get("groupName", "Main"))
                if clue and answer:
                    puzzles.append({"clue": clue, "answer": answer})
        if puzzles:
            groups.append({"name": "All Puzzles", "puzzles": puzzles})
    
    # Format 4: Direct puzzle fields
    else:
        # Try to find any clues and answers at any nesting level
        def extract_recursive(obj, depth=0):
            if depth > 10:
                return [], ""
            found_puzzles = []
            found_theme = ""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.lower() in ("clue", "question", "definition", "description"):
                        if "answer" in obj or "solution" in obj or "word" in obj:
                            ans = obj.get("answer", obj.get("solution", obj.get("word", "")))
                            found_puzzles.append({"clue": str(v), "answer": str(ans)})
                    elif k.lower() in ("theme", "title", "worldname", "name") and isinstance(v, str):
                        found_theme = v
                    elif isinstance(v, (dict, list)):
                        sub_puzzles, sub_theme = extract_recursive(v, depth+1)
                        found_puzzles.extend(sub_puzzles)
                        if sub_theme and not found_theme:
                            found_theme = sub_theme
            elif isinstance(obj, list):
                for item in obj:
                    sub_puzzles, sub_theme = extract_recursive(item, depth+1)
                    found_puzzles.extend(sub_puzzles)
                    if sub_theme and not found_theme:
                        found_theme = sub_theme
            return found_puzzles, found_theme
        
        puzzles, theme = extract_recursive(data)
        if puzzles:
            groups.append({"name": "Puzzles", "puzzles": puzzles})
    
    return {"theme": theme, "world": world, "groups": groups}


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
            "description": "Daily puzzle answers fetched automatically from CodyCross API",
            "lastUpdated": datetime.now().strftime("%Y-%m-%d"),
            "dataSource": "CodyCross API",
            "encryption": "AES-256-CBC",
            "apiEndpoint": DEV_API_BASE,
            "updateMethod": "GitHub Actions (automated daily fetch + decrypt)"
        },
        "answers": []
    }


def save_answer_entry(entry):
    """Add an answer entry to answers.json."""
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
    
    print(f"  [+] Updated {ANSWERS_FILE}")
    print(f"  [+] Date: {today_str}, Theme: {entry.get('theme', 'N/A')}, Groups: {len(entry.get('groups', []))}")


# ============================================================
# MAIN PIPELINE
# ============================================================

def fetch_and_decrypt(mundo_num=1, aes_key=None):
    """Fetch puzzle data from API and decrypt with AES key."""
    
    print(f"\n[*] Fetching puzzle data for world {mundo_num}...")
    response = fetch_puzzle_world(mundo_num)
    
    if not response:
        print("  [!] Failed to fetch from dev API")
        return None
    
    records = response.get("Records", [])
    if not records:
        # Check for direct data
        if response.get("Ok"):
            print("  [+] API responded Ok=true but no Records field")
            print(f"  [+] Keys: {list(response.keys())}")
            # Try to use the whole response as data
            records = [json.dumps(response)]
        else:
            print("  [!] No records in response")
            return None
    
    print(f"  [+] Got {len(records)} record(s)")
    
    if not aes_key:
        print("  [!] No AES key available — cannot decrypt")
        print("  [!] Save encrypted data for later decryption")
        
        for i, record in enumerate(records):
            if isinstance(record, str) and len(record) > 50:
                b64_clean = record.replace("\\u002B", "+")
                encrypted_bytes = base64.b64decode(b64_clean)
                raw_path = os.path.join(DATA_DIR, f"encrypted_record_{i}.bin")
                with open(raw_path, "wb") as f:
                    f.write(encrypted_bytes)
                print(f"  [+] Saved encrypted record {i} ({len(encrypted_bytes)} bytes) to {raw_path}")
        
        return None
    
    # Decrypt each record
    print(f"\n[*] Decrypting with AES-256-CBC key...")
    
    decrypted_records = []
    for i, record in enumerate(records):
        if not isinstance(record, str):
            print(f"  Record {i}: Not a string, skipping")
            continue
        
        text = try_decrypt_with_key(record, aes_key)
        if text:
            print(f"  Record {i}: Decrypted to {len(text)} chars")
            decrypted_records.append(text)
            
            # Save decrypted data
            os.makedirs(DATA_DIR, exist_ok=True)
            dec_path = os.path.join(DATA_DIR, f"decrypted_record_{i}.json")
            try:
                parsed = json.loads(text)
                with open(dec_path, "w") as f:
                    json.dump(parsed, f, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                with open(dec_path, "w") as f:
                    f.write(text)
        else:
            print(f"  Record {i}: Decryption failed (wrong key?)")
    
    return decrypted_records


def run_demo_mode():
    """Generate demo data to show the website works."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Sample puzzle data (realistic structure)
    entry = {
        "date": today_str,
        "theme": "Demo — Awaiting AES Key Extraction",
        "world": 1,
        "groups": [
            {
                "name": "Getting Started",
                "puzzles": [
                    {"clue": "This website auto-updates daily with puzzle answers", "answer": "AUTO UPDATE"},
                    {"clue": "The encryption used by CodyCross API", "answer": "AES 256 CBC"},
                ]
            },
            {
                "name": "Next Steps",
                "puzzles": [
                    {"clue": "Run the Frida Key Extraction workflow once", "answer": "EXTRACT KEY"},
                    {"clue": "Add the key as a GitHub Secret called", "answer": "GAME AES KEY"},
                    {"clue": "This workflow will then auto-fetch daily", "answer": "DAILY EXTRACT"},
                ]
            }
        ]
    }
    
    save_answer_entry(entry)
    print("\n  [+] Demo data written — website will show sample answers")
    return True


def main():
    print("=" * 60)
    print("  CodyCross Daily Answer Fetcher v2.0")
    print("  Data Source: CodyCross API")
    print("=" * 60)
    
    # Parse arguments
    mundo = 1
    demo = False
    
    for arg in sys.argv[1:]:
        if arg == "--mundo":
            idx = sys.argv.index("--mundo")
            if idx + 1 < len(sys.argv):
                mundo = int(sys.argv[idx + 1])
        elif arg == "--demo":
            demo = True
    
    aes_key = get_aes_key()
    
    if aes_key:
        print(f"\n[+] AES key loaded: {aes_key.hex()[:16]}... ({len(aes_key)} bytes)")
    else:
        print("\n[!] No GAME_AES_KEY environment variable set")
        print("[!] Decryption will not work until the key is extracted")
    
    if demo:
        print("\n[!] Running in DEMO mode")
        return run_demo_mode()
    
    # Try multiple worlds to find the daily puzzle
    today_str = datetime.now().strftime("%Y-%m-%d")
    success = False
    
    # Calculate which world corresponds to today
    # CodyCross releases daily puzzles cycling through worlds
    day_of_year = (datetime.now() - datetime(datetime.now().year, 1, 1)).days
    
    # Try the dev API with a few world numbers
    worlds_to_try = [mundo, 7, 15, 20]
    if mundo == 1:
        worlds_to_try = [1, 7, 15, 20, 30]
    
    for w in worlds_to_try:
        print(f"\n{'─' * 40}")
        print(f"[*] Trying world {w}...")
        
        decrypted = fetch_and_decrypt(w, aes_key)
        
        if decrypted:
            # Parse the first record that looks like puzzle data
            for text in decrypted:
                parsed = parse_decrypted_puzzle(text)
                if parsed and parsed.get("groups"):
                    entry = {
                        "date": today_str,
                        "theme": parsed["theme"],
                        "world": w,
                        "groups": parsed["groups"]
                    }
                    save_answer_entry(entry)
                    success = True
                    break
        
        if success:
            break
    
    # Also try production API endpoints
    if not success:
        print(f"\n[*] Trying production API endpoints...")
        
        for endpoint_name, fetch_fn in [
            ("Today's Crossword", fetch_todays_crossword),
            ("Daily Puzzle", fetch_daily_puzzle),
        ]:
            print(f"\n  [{endpoint_name}]")
            resp = fetch_fn()
            if resp:
                print(f"  [+] Got response: {list(resp.keys()) if isinstance(resp, dict) else type(resp)}")
                if aes_key and isinstance(resp, dict):
                    records = resp.get("Records", resp.get("records", []))
                    if records:
                        for record in records:
                            if isinstance(record, str) and aes_key:
                                text = try_decrypt_with_key(record, aes_key)
                                if text:
                                    parsed = parse_decrypted_puzzle(text)
                                    if parsed and parsed.get("groups"):
                                        entry = {
                                            "date": today_str,
                                            "theme": parsed["theme"],
                                            "world": mundo,
                                            "groups": parsed["groups"]
                                        }
                                        save_answer_entry(entry)
                                        success = True
                                        break
    
    # If still no success, try demo data so website shows something
    if not success:
        print("\n[!] Could not fetch and decrypt real puzzle data")
        print("[!] This is expected if:")
        print("    - No GAME_AES_KEY is set (run frida-key-extract workflow)")
        print("    - The API endpoints have changed")
        print("    - Network issues")
        print("\n[*] Creating placeholder entry...")
        entry = {
            "date": today_str,
            "theme": "Awaiting AES Key Extraction",
            "world": mundo,
            "groups": []
        }
        save_answer_entry(entry)
    
    # Always fetch game texts (unencrypted endpoint)
    print(f"\n[*] Fetching game texts (unencrypted)...")
    text_data = fetch_text_list()
    if text_data and text_data.get("Records"):
        records = text_data["Records"]
        game_texts = {}
        for rec in records:
            ident = rec.get("Identificador", "")
            valor = rec.get("Valor", {})
            if isinstance(valor, dict) and "en" in valor:
                game_texts[ident] = valor["en"]
        
        os.makedirs(DATA_DIR, exist_ok=True)
        texts_path = os.path.join(DATA_DIR, "game_texts.json")
        with open(texts_path, "w") as f:
            json.dump(game_texts, f, indent=2, ensure_ascii=False)
        print(f"  [+] Saved {len(game_texts)} game text entries")
    
    print(f"\n{'=' * 60}")
    print(f"  Done! Check {DATA_DIR}/ for output files.")
    print(f"{'=' * 60}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
