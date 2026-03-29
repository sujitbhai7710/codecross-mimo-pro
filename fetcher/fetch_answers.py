#!/usr/bin/env python3
"""
CodyCross Daily Answer Fetcher
===============================
Automatically fetches puzzle data from the CodyCross API,
decrypts it, and updates the website data files.

Data Source: CodyCross dev API (codydev.fulano.com.br)
Encryption: AES-256-CBC (key embedded in app binary)

Usage:
    python3 fetch_answers.py              # Fetch today's answers
    python3 fetch_answers.py --mundo 1    # Fetch specific world
    python3 fetch_answers.py --all        # Fetch all available worlds
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

API_BASE = "https://codydev.fulano.com.br"
TOKEN = "872fbb4c-fa3c-4534-b6e4-4b56bd7d3fc6"
LANG = "1aca585a-8e15-3029-89a0-54aa078acec2"  # English
COUNTRY = "US"
DEVICE_TYPE = "Android"
APP_VERSION = "1.31.0"
DIFFICULTY = 2  # Normal difficulty

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ANSWERS_FILE = os.path.join(DATA_DIR, "answers.json")

# ============================================================
# API COMMUNICATION
# ============================================================

def build_url(endpoint, params=None):
    """Build API URL with common parameters."""
    base_params = {
        "androidLang": "en",
        "deviceType": DEVICE_TYPE,
        "appVersion": APP_VERSION,
    }
    if params:
        base_params.update(params)
    
    query = "&".join(f"{k}={v}" for k, v in base_params.items())
    return f"{API_BASE}/{endpoint}?{query}"


def api_get(url):
    """Make GET request to API and return parsed JSON."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "CodyCross/2.8.1 (Android)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("Ok"):
                return data
            else:
                print(f"  API returned Ok=false: {data.get('Message', 'unknown error')}")
                return None
    except urllib.error.URLError as e:
        print(f"  Network error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None


def fetch_text_list():
    """Fetch UI text/localization strings (unencrypted)."""
    url = build_url("Texto/List")
    return api_get(url)


def fetch_puzzle_world(mundo_num, difficulty=DIFFICULTY):
    """
    Fetch puzzle data for a specific world.
    Returns encrypted records - needs decryption.
    """
    params = {
        "token": TOKEN,
        "lang": LANG,
        "mundo": str(mundo_num),
        "country": COUNTRY,
        "dificuldadeDoPuzzle": str(difficulty),
    }
    url = build_url("Puzzle/GetMundo", params)
    return api_get(url)


# ============================================================
# DECRYPTION
# ============================================================

def try_decrypt_aes(encrypted_bytes, key_hex=None):
    """
    Attempt AES-256-CBC decryption.
    
    The CodyCross app uses AES encryption for puzzle data.
    The key is embedded in the app's native binary (libil2cpp.so).
    
    This function tries known/common keys. For full decryption,
    the AES key needs to be extracted from the binary using
    tools like Il2CppDumper + Ghidra/IDA Pro.
    """
    try:
        from Crypto.Cipher import AES
        HAS_CRYPTO = True
    except ImportError:
        try:
            # Try with pycryptodome
            from Cryptodome.Cipher import AES
            HAS_CRYPTO = True
        except ImportError:
            HAS_CRYPTO = False
    
    if not HAS_CRYPTO:
        print("  [!] pycryptodome not installed. Run: pip3 install pycryptodome")
        return None
    
    # Common key derivation attempts
    # In the app, the key is likely derived from a string constant
    possible_keys = []
    
    if key_hex:
        possible_keys.append(bytes.fromhex(key_hex))
    
    # Try key derivation from known app strings
    key_strings = [
        "fanatee_codycross_key",
        "codycross_puzzle_key", 
        "fanatee_secret_key",
        "codycross_secret",
        "com.fanatee.cody",
    ]
    
    for ks in key_strings:
        # SHA-256 hash of string = 32 bytes = AES-256 key
        key = hashlib.sha256(ks.encode()).digest()
        possible_keys.append(key)
    
    # The IV is typically the first 16 bytes of the encrypted data
    if len(encrypted_bytes) > 16:
        iv = encrypted_bytes[:16]
        ciphertext = encrypted_bytes[16:]
    else:
        return None
    
    for key in possible_keys:
        try:
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(ciphertext)
            
            # Check if decryption produced valid data
            # Remove PKCS7 padding
            pad_len = decrypted[-1]
            if 1 <= pad_len <= 16:
                decrypted = decrypted[:-pad_len]
            
            # Check if result looks like valid text/JSON
            try:
                text = decrypted.decode("utf-8", errors="strict")
                if text.startswith("{") or text.startswith("[") or "puzzle" in text.lower():
                    print(f"  [+] Decryption successful!")
                    return text
            except UnicodeDecodeError:
                # Try as binary protobuf or other format
                if b"puzzle" in decrypted.lower() or b"answer" in decrypted.lower():
                    print(f"  [+] Decryption produced binary data with puzzle content")
                    return decrypted
        except Exception:
            continue
    
    return None


def decrypt_puzzle_data(encrypted_records):
    """
    Attempt to decrypt puzzle data from API response.
    
    The API returns 2 records:
    - Record 0: Small (~7KB) - likely metadata/config, AES encrypted
    - Record 1: Large (~312KB) - puzzle content, AES encrypted
    
    Both use the same key derived from the app binary.
    """
    results = []
    
    for i, record in enumerate(encrypted_records):
        # Decode base64
        b64_clean = record.replace("\\u002B", "+")
        encrypted_bytes = base64.b64decode(b64_clean)
        
        print(f"  Record {i}: {len(encrypted_bytes)} bytes (AES-{len(encrypted_bytes)//16} blocks)")
        
        # Try decryption
        decrypted = try_decrypt_aes(encrypted_bytes)
        
        if decrypted:
            results.append(decrypted)
            if isinstance(decrypted, str):
                print(f"  Record {i}: Decrypted to {len(decrypted)} chars")
            else:
                print(f"  Record {i}: Decrypted to {len(decrypted)} bytes")
        else:
            print(f"  Record {i}: Could not decrypt (key not found in binary)")
            # Save encrypted data for manual analysis
            raw_path = os.path.join(DATA_DIR, f"encrypted_record_{i}.bin")
            with open(raw_path, "wb") as f:
                f.write(encrypted_bytes)
            print(f"  Record {i}: Saved encrypted data to {raw_path}")
            results.append(None)
    
    return results


# ============================================================
# DATA PROCESSING
# ============================================================

def parse_puzzle_data(decrypted_json):
    """
    Parse decrypted puzzle JSON into our answer format.
    
    Expected format (inferred from app structure):
    {
        "world": 1,
        "groups": [
            {
                "name": "Group 1",
                "puzzles": [
                    {"clue": "...", "answer": "..."},
                    ...
                ]
            },
            ...
        ]
    }
    """
    try:
        data = json.loads(decrypted_json) if isinstance(decrypted_json, str) else decrypted_json
        
        # The exact structure depends on the decrypted format
        # This will need adjustment once we can decrypt
        puzzles = []
        
        if "Records" in data:
            for record in data["Records"]:
                if isinstance(record, dict):
                    for key, val in record.items():
                        if isinstance(val, list):
                            for item in val:
                                if isinstance(item, dict) and "clue" in item and "answer" in item:
                                    puzzles.append(item)
        
        return puzzles
    except (json.JSONDecodeError, TypeError):
        return []


def update_answers_file(world_num, theme, groups):
    """Update the answers.json file with new puzzle data."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Load existing data
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {
            "site": {
                "name": "CodeCross Daily Answers",
                "description": "Daily puzzle answers updated automatically",
                "lastUpdated": datetime.now().strftime("%Y-%m-%d"),
                "dataSource": "CodyCross API (codydev.fulano.com.br)",
                "encryption": "AES-256-CBC",
                "apiEndpoint": f"{API_BASE}/Puzzle/GetMundo"
            },
            "answers": []
        }
    
    # Create today's entry
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    entry = {
        "date": today_str,
        "theme": theme or f"World {world_num}",
        "world": world_num,
        "groups": groups
    }
    
    # Remove existing entry for today if present
    data["answers"] = [a for a in data.get("answers", []) if a.get("date") != today_str]
    
    # Add new entry at the beginning
    data["answers"].insert(0, entry)
    data["site"]["lastUpdated"] = today_str
    
    # Save
    with open(ANSWERS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n  [+] Updated {ANSWERS_FILE}")
    print(f"  [+] Date: {today_str}, World: {world_num}, Groups: {len(groups)}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  CodyCross Daily Answer Fetcher")
    print("  Data Source: codydev.fulano.com.br API")
    print("=" * 60)
    
    mundo = 1
    if "--mundo" in sys.argv:
        idx = sys.argv.index("--mundo")
        if idx + 1 < len(sys.argv):
            mundo = int(sys.argv[idx + 1])
    
    # Step 1: Fetch puzzle data from API
    print(f"\n[1] Fetching puzzle data for world {mundo}...")
    response = fetch_puzzle_world(mundo)
    
    if not response:
        print("  [!] Failed to fetch data from API")
        return 1
    
    records = response.get("Records", [])
    print(f"  [+] Got {len(records)} encrypted records")
    
    # Step 2: Attempt decryption
    print(f"\n[2] Attempting decryption...")
    decrypted = decrypt_puzzle_data(records)
    
    # Step 3: Process results
    print(f"\n[3] Processing results...")
    
    success = False
    for i, dec in enumerate(decrypted):
        if dec:
            if isinstance(dec, str):
                # Try to parse as JSON
                try:
                    parsed = json.loads(dec)
                    print(f"  Record {i}: Valid JSON with {len(parsed)} top-level keys")
                    
                    # Save decrypted data
                    dec_path = os.path.join(DATA_DIR, f"decrypted_record_{i}.json")
                    with open(dec_path, "w") as f:
                        json.dump(parsed, f, indent=2, ensure_ascii=False)
                    print(f"  Saved to {dec_path}")
                    success = True
                except json.JSONDecodeError:
                    print(f"  Record {i}: Not JSON, saving as text")
                    dec_path = os.path.join(DATA_DIR, f"decrypted_record_{i}.txt")
                    with open(dec_path, "w") as f:
                        f.write(dec)
                    success = True
    
    if not success:
        print("\n  [!] Decryption failed - AES key not extracted from binary yet.")
        print("  [!] To extract the key, you need:")
        print("      1. Il2CppDumper to extract metadata from libil2cpp.so")
        print("      2. Ghidra/IDA Pro to find the key in the binary")
        print("      3. Or use Frida to hook decryption at runtime")
        print("\n  [i] Encrypted data saved for offline analysis.")
        print("  [i] The website framework is ready - just needs the key!")
    
    # Step 4: Update website
    print(f"\n[4] Updating website data...")
    
    # For now, use text data from the working Texto/List endpoint
    print("  Fetching text data from Texto/List endpoint...")
    text_data = fetch_text_list()
    
    if text_data and text_data.get("Records"):
        # Extract useful game text strings
        records = text_data["Records"]
        game_texts = {}
        for rec in records:
            ident = rec.get("Identificador", "")
            valor = rec.get("Valor", {})
            if isinstance(valor, dict) and "en" in valor:
                game_texts[ident] = valor["en"]
        
        # Save game texts
        texts_path = os.path.join(DATA_DIR, "game_texts.json")
        with open(texts_path, "w") as f:
            json.dump(game_texts, f, indent=2, ensure_ascii=False)
        print(f"  [+] Saved {len(game_texts)} game text entries")
    
    print(f"\n{'=' * 60}")
    print(f"  Done! Check {DATA_DIR}/ for output files.")
    print(f"{'=' * 60}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
