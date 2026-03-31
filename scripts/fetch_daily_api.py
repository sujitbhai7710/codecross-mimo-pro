#!/usr/bin/env python3
"""
CodyCross Daily Fetcher - Uses Player Token from Shizuku Extract
=================================================================
Fetches Daily Crossword + Daily Password answers from CodyCross API
using the player token extracted via Shizuku.

REQUIRES: player_token.json from shizuku_extract.sh

FILE PLACEMENT:
  Put this file in: ~/codycross/fetch_daily_api.py
  (same folder as shizuku_extract.sh)

USAGE:
  cd ~/codycross
  python3 fetch_daily_api.py
  python3 fetch_daily_api.py --token "YOUR_TOKEN"
  python3 fetch_daily_api.py --player-id "YOUR_ID"
"""

import json
import sys
import os
import time
import argparse
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

# ============================================================
# Configuration
# ============================================================

API_BASE = "https://game.codycross-game.com"
DEV_API_BASE = "https://codydev.fulano.com.br"
APP_TOKEN = "872fbb4c-fa3c-4534-b6e4-4b56bd7d3fc6"
USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 13; Pixel 7 Build/TQ3A.230901.001)"

# Output directory (same folder as this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "daily_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Colors for terminal
class C:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log(msg, color=None):
    prefix = f"{color}" if color else ""
    suffix = C.NC if color else ""
    print(f"{prefix}{msg}{suffix}")

# ============================================================
# API Helper
# ============================================================

def api_request(endpoint, params=None, method="GET", base_url=None, token=None, app_token=None):
    """Make HTTP request to CodyCross API"""
    url_base = base_url or API_BASE
    url = f"{url_base}{endpoint}"
    
    if params:
        # Filter out None values
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url += "?" + urllib.parse.urlencode(filtered)
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "X-Unity-Version": "2021.3.20f1",
        "Accept-Encoding": "gzip",
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if app_token:
        headers["X-App-Token"] = app_token
    
    req = urllib.request.Request(url, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            # Try gzip decompress
            if data[:2] == b'\x1f\x8b':
                import gzip
                data = gzip.decompress(data)
            return json.loads(data.decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode('utf-8', errors='replace')
        except:
            pass
        log(f"  HTTP {e.code} for {endpoint}: {body[:200]}", C.RED)
        return {"error": e.code, "body": body[:500]}
    except Exception as e:
        log(f"  Error for {endpoint}: {str(e)}", C.RED)
        return {"error": str(e)}

# ============================================================
# Load Player Credentials
# ============================================================

def load_credentials():
    """Load player token and ID from extracted JSON"""
    token_file = os.path.join(SCRIPT_DIR, "extracted", "player_token.json")
    
    if not os.path.exists(token_file):
        return None, None, None, None
    
    with open(token_file, 'r') as f:
        data = json.load(f)
    
    return (
        data.get("player_token", ""),
        data.get("player_id", ""),
        data.get("player_name", ""),
        data.get("device_id", "")
    )

# ============================================================
# Daily Password Fetch
# ============================================================

def fetch_daily_password(token, player_id, device_id):
    """Fetch today's password puzzle from API"""
    log("\n" + "="*50, C.BLUE)
    log("FETCHING DAILY PASSWORD", C.BLUE)
    log("="*50, C.BLUE)
    
    today = datetime.now().strftime("%Y-%m-%d")
    results = []
    
    # Try different endpoint patterns for Today's Password
    endpoints = [
        ("/TodaysPassword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "appVersion": "1.0.0",
            "date": today,
        }),
        ("/TodaysPassword/Get", {
            "appVersion": "1.0.0",
        }),
        ("/Password/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "date": today,
        }),
        ("/DailyPassword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
        }),
    ]
    
    for endpoint, params in endpoints:
        log(f"\n  Trying: {endpoint}", C.CYAN)
        log(f"  Params: {json.dumps(params, indent=4)}", C.YELLOW)
        
        # Try with token
        resp = api_request(endpoint, params=params, token=token, app_token=APP_TOKEN)
        log(f"  Response: {json.dumps(resp, indent=2)[:500]}", C.GREEN if resp.get("Ok") else C.YELLOW)
        
        if resp.get("Ok") or resp.get("ok"):
            results.append({"endpoint": endpoint, "data": resp})
            log(f"  SUCCESS via {endpoint}!", C.GREEN)
            break
        
        # Try with just app token (no player token)
        resp2 = api_request(endpoint, params=params, app_token=APP_TOKEN)
        if resp2.get("Ok") or resp2.get("ok"):
            results.append({"endpoint": endpoint, "data": resp2})
            log(f"  SUCCESS (app token only) via {endpoint}!", C.GREEN)
            break
        
        # Try with different header combos
        resp3 = api_request(endpoint, params=params, token=token)
        if resp3.get("Ok") or resp3.get("ok"):
            results.append({"endpoint": endpoint, "data": resp3})
            log(f"  SUCCESS (no app token) via {endpoint}!", C.GREEN)
            break
        
        results.append({"endpoint": endpoint, "data": resp})
    
    return results

# ============================================================
# Daily Crossword Fetch
# ============================================================

def fetch_daily_crossword(token, player_id, device_id):
    """Fetch today's daily crossword from API"""
    log("\n" + "="*50, C.BLUE)
    log("FETCHING DAILY CROSSWORD", C.BLUE)
    log("="*50, C.BLUE)
    
    today = datetime.now()
    date_str = today.strftime("%Y_%m_%d")
    date_dash = today.strftime("%Y-%m-%d")
    results = []
    
    # Try various daily crossword endpoints
    endpoints = [
        # Pattern: /DailyCrossword/Get
        ("/DailyCrossword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "date": date_dash,
            "appVersion": "1.0.0",
            "language": "en",
        }),
        # Pattern: /TodayCrossword/Get
        ("/TodayCrossword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "appVersion": "1.0.0",
        }),
        # Pattern: /Crossword/GetDaily
        ("/Crossword/GetDaily", {
            "playerId": player_id,
            "appVersion": "1.0.0",
        }),
        # Pattern: /Daily/Get
        ("/Daily/Get", {
            "playerId": player_id,
            "appVersion": "1.0.0",
        }),
        # Pattern: /Event/GetDaily
        ("/Event/GetDaily", {
            "playerId": player_id,
            "appVersion": "1.0.0",
        }),
        # Try with date in different formats
        ("/TodayCrossword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "date": date_str,
            "appVersion": "1.0.0",
            "size": "small",
            "language": "en",
        }),
        # Try getting small and midsize separately
        ("/TodayCrossword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "date": date_dash,
            "appVersion": "1.0.0",
            "size": "small",
        }),
        ("/TodayCrossword/Get", {
            "playerId": player_id,
            "deviceId": device_id,
            "date": date_dash,
            "appVersion": "1.0.0",
            "size": "midsize",
        }),
    ]
    
    for endpoint, params in endpoints:
        log(f"\n  Trying: {endpoint}", C.CYAN)
        log(f"  Params: {json.dumps(params, indent=4)}", C.YELLOW)
        
        # Try with full auth
        resp = api_request(endpoint, params=params, token=token, app_token=APP_TOKEN)
        status = "OK" if (resp.get("Ok") or resp.get("ok") or not resp.get("error")) else "FAIL"
        log(f"  [{status}] Response: {json.dumps(resp, indent=2)[:500]}", 
            C.GREEN if status == "OK" else C.YELLOW)
        
        if resp.get("Ok") or resp.get("ok"):
            results.append({"endpoint": endpoint, "data": resp})
            log(f"  SUCCESS via {endpoint}!", C.GREEN)
            break
        
        results.append({"endpoint": endpoint, "status": status, "data": resp})
    
    return results

# ============================================================
# Explore Authenticated Endpoints
# ============================================================

def explore_auth_endpoints(token, player_id, device_id):
    """Try various authenticated endpoints to see what's available"""
    log("\n" + "="*50, C.BLUE)
    log("EXPLORING AUTHENTICATED ENDPOINTS", C.BLUE)
    log("="*50, C.BLUE)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    endpoints = [
        ("/Player/GetProfile", {"playerId": player_id}),
        ("/Player/GetData", {"playerId": player_id, "appVersion": "1.0.0"}),
        ("/Config/Get", {"appVersion": "1.0.0"}),
        ("/Puzzle/GetSettings", {"playerId": player_id, "appVersion": "1.0.0"}),
        ("/Player/GetPuzzleSettings", {"playerId": player_id}),
        ("/Daily/GetStatus", {"playerId": player_id, "date": today}),
        ("/Event/GetList", {"playerId": player_id, "appVersion": "1.0.0"}),
        ("/Store/GetProducts", {"appVersion": "1.0.0"}),
        ("/Achievement/GetList", {"playerId": player_id}),
        ("/Player/GetStats", {"playerId": player_id}),
        ("/Progress/Get", {"playerId": player_id, "appVersion": "1.0.0"}),
        ("/Crossword/GetArchive", {"playerId": player_id, "month": today[:7]}),
        ("/Crossword/GetAvailable", {"playerId": player_id}),
        ("/TodaysPassword/GetHistory", {"playerId": player_id, "days": 7}),
    ]
    
    discovered = []
    
    for endpoint, params in endpoints:
        resp = api_request(endpoint, params=params, token=token, app_token=APP_TOKEN)
        
        # Check if endpoint exists (not 404)
        is_error = resp.get("error")
        has_data = resp.get("Ok") or resp.get("ok") or (not is_error and len(resp) > 1)
        
        status_icon = C.GREEN + "[OK]" if has_data else C.RED + "[--]"
        log(f"  {status_icon}{C.NC} {endpoint}", )
        
        if has_data:
            # Only print first 200 chars of response
            resp_str = json.dumps(resp, indent=2)[:200]
            log(f"       {resp_str}", C.CYAN)
            discovered.append({
                "endpoint": endpoint,
                "params": params,
                "response_keys": list(resp.keys()) if isinstance(resp, dict) else [],
                "ok": resp.get("Ok") or resp.get("ok", False),
            })
        elif is_error and isinstance(is_error, int) and is_error != 404:
            # Non-404 errors mean endpoint exists but needs something else
            discovered.append({
                "endpoint": endpoint,
                "params": params,
                "error_code": is_error,
                "note": "Exists but returned error"
            })
    
    return discovered

# ============================================================
# Try Dev API as well
# ============================================================

def try_dev_api(token, player_id, device_id):
    """Try the same endpoints on the dev API"""
    log("\n" + "="*50, C.BLUE)
    log("TRYING DEV API", C.BLUE)
    log("="*50, C.BLUE)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    endpoints = [
        ("/TodaysPassword/Get", {"playerId": player_id, "date": today, "appVersion": "1.0.0"}),
        ("/TodayCrossword/Get", {"playerId": player_id, "appVersion": "1.0.0"}),
        ("/Config/Get", {"appVersion": "1.0.0"}),
    ]
    
    results = []
    for endpoint, params in endpoints:
        resp = api_request(endpoint, params=params, token=token, 
                          app_token=APP_TOKEN, base_url=DEV_API_BASE)
        status = "OK" if (resp.get("Ok") or resp.get("ok") or not resp.get("error")) else "FAIL"
        log(f"  [{status}] {endpoint}", C.GREEN if status == "OK" else C.YELLOW)
        log(f"       {json.dumps(resp, indent=2)[:300]}", C.CYAN)
        results.append({"endpoint": endpoint, "data": resp})
    
    return results

# ============================================================
# Save Results
# ============================================================

def save_results(password_results, crossword_results, discovered_endpoints, dev_results):
    """Save all results to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save password results
    if password_results:
        pw_file = os.path.join(OUTPUT_DIR, f"password_{timestamp}.json")
        with open(pw_file, 'w') as f:
            json.dump(password_results, f, indent=2, default=str)
        log(f"\n  Password results saved: {pw_file}", C.GREEN)
    
    # Save crossword results
    if crossword_results:
        cw_file = os.path.join(OUTPUT_DIR, f"crossword_{timestamp}.json")
        with open(cw_file, 'w') as f:
            json.dump(crossword_results, f, indent=2, default=str)
        log(f"  Crossword results saved: {cw_file}", C.GREEN)
    
    # Save discovered endpoints
    if discovered_endpoints:
        disc_file = os.path.join(OUTPUT_DIR, f"endpoints_{timestamp}.json")
        with open(disc_file, 'w') as f:
            json.dump(discovered_endpoints, f, indent=2, default=str)
        log(f"  Discovered endpoints saved: {disc_file}", C.GREEN)
    
    # Save dev API results
    if dev_results:
        dev_file = os.path.join(OUTPUT_DIR, f"dev_api_{timestamp}.json")
        with open(dev_file, 'w') as f:
            json.dump(dev_results, f, indent=2, default=str)
        log(f"  Dev API results saved: {dev_file}", C.GREEN)

# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="CodyCross Daily Fetcher")
    parser.add_argument("--token", help="Player token (overrides extracted)")
    parser.add_argument("--player-id", help="Player ID (overrides extracted)")
    parser.add_argument("--device-id", help="Device ID (overrides extracted)")
    parser.add_argument("--explore-only", action="store_true", help="Only explore endpoints, don't fetch daily")
    parser.add_argument("--dev", action="store_true", help="Also try dev API")
    args = parser.parse_args()
    
    log("=" * 50, C.BLUE)
    log("  CodyCross Daily Fetcher v1.0", C.BLUE)
    log("  Using Shizuku-extracted credentials", C.BLUE)
    log("=" * 50, C.BLUE)
    
    # Load credentials
    token = args.token
    player_id = args.player_id
    device_id = args.device_id
    player_name = ""
    
    if not token or not player_id:
        log("\n  Loading credentials from player_token.json...", C.YELLOW)
        ext_token, ext_pid, ext_name, ext_did = load_credentials()
        
        token = token or ext_token
        player_id = player_id or ext_pid
        player_name = player_name or ext_name
        device_id = device_id or ext_did
    
    # Status display
    log(f"\n  Credentials:", C.CYAN)
    log(f"    Player Token: {token[:30] + '...' if token and len(token) > 30 else token or 'NOT SET'}", C.CYAN)
    log(f"    Player ID:    {player_id or 'NOT SET'}", C.CYAN)
    log(f"    Player Name:  {player_name or 'NOT SET'}", C.CYAN)
    log(f"    Device ID:    {device_id or 'NOT SET'}", C.CYAN)
    
    if not token and not player_id:
        log("\n" + "!" * 50, C.RED)
        log("  NO CREDENTIALS FOUND!", C.RED)
        log("  Run shizuku_extract.sh first to get player token.", C.RED)
        log("  Or use --token and --player-id flags.", C.RED)
        log("!" * 50, C.RED)
        log("\n  You can also run with just --explore-only to test", C.YELLOW)
        log("  unauthenticated endpoints.", C.YELLOW)
        
        # Still do a basic config check
        log("\n  Checking public config...", C.YELLOW)
        config = api_request("/Config/Get", {"appVersion": "1.0.0"}, app_token=APP_TOKEN)
        log(f"  Config response: {json.dumps(config, indent=2)[:500]}", C.CYAN)
        return
    
    # Step 1: Fetch daily password
    password_results = []
    if not args.explore_only:
        password_results = fetch_daily_password(token, player_id, device_id)
    
    # Step 2: Fetch daily crossword
    crossword_results = []
    if not args.explore_only:
        crossword_results = fetch_daily_crossword(token, player_id, device_id)
    
    # Step 3: Explore authenticated endpoints
    discovered = explore_auth_endpoints(token, player_id, device_id)
    
    # Step 4: Try dev API
    dev_results = []
    if args.dev:
        dev_results = try_dev_api(token, player_id, device_id)
    
    # Save everything
    save_results(password_results, crossword_results, discovered, dev_results)
    
    # Final summary
    log("\n" + "=" * 50, C.GREEN)
    log("  DONE!", C.GREEN)
    log("=" * 50, C.GREEN)
    log(f"  Results saved to: {OUTPUT_DIR}/", C.GREEN)
    log(f"  Check endpoint discovery results for working APIs.", C.GREEN)
    
    # Count successes
    successes = sum(1 for r in password_results + crossword_results if r.get("data", {}).get("Ok") or r.get("data", {}).get("ok"))
    discovered_count = len(discovered)
    
    log(f"\n  Password endpoints tested: {len(password_results)} (success: {successes})", C.CYAN)
    log(f"  Crossword endpoints tested: {len(crossword_results)}", C.CYAN)
    log(f"  Auth endpoints discovered: {discovered_count}", C.CYAN)
    
    if successes > 0:
        log(f"\n  {C.GREEN}Working endpoints found! Check output files for data.{C.NC}")
    else:
        log(f"\n  {C.YELLOW}No working daily endpoints found yet.{C.NC}")
        log(f"  {C.YELLOW}Check discovered endpoints - some may need different params.{C.NC}")
        log(f"  {C.YELLOW}The daily crossword data may still come from .cody bundles.{C.NC}")

if __name__ == "__main__":
    main()
