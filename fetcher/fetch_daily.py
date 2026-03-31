#!/usr/bin/env python3
"""
CodyCross Daily Games Scraper
===============================
Scrapes daily crossword (Small + Midsize) and password answers
from levelhacks.com (structured JSON-LD data).

Data source: https://www.levelhacks.com/codycross/daily/{YYYY-MM-DD}/
Password: https://www.codycrosssolutions.com/codycross-password

Usage:
    python3 fetch_daily.py              # Fetch today's answers
    python3 fetch_daily.py 2026-03-31   # Fetch specific date
    python3 fetch_daily.py --week       # Fetch last 7 days
"""

import json
import os
import sys
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DAILY_FILE = os.path.join(DATA_DIR, "daily_answers.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

def fetch_url(url, timeout=30):
    """Fetch a URL and return the HTML content."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def extract_jsonld(html):
    """Extract JSON-LD structured data from HTML."""
    # Find all JSON-LD script blocks (with or without quotes around type)
    pattern = r'<script[^>]*type=["\']?application/ld\+json["\']?[^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL)
    
    results = []
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict):
                results.append(data)
            elif isinstance(data, list):
                results.extend(data)
        except json.JSONDecodeError:
            pass
    
    return results

def parse_daily_crossword(date_str):
    """Parse daily crossword data for a specific date."""
    url = f"https://www.levelhacks.com/codycross/daily/{date_str}/"
    print(f"  Fetching: {url}")
    
    try:
        html = fetch_url(url)
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None
    
    jsonld_data = extract_jsonld(html)
    
    result = {
        "date": date_str,
        "small": {"clues": []},
        "midsize": {"clues": []},
    }
    
    for item in jsonld_data:
        if not isinstance(item, dict):
            continue
        
        name = item.get("name", "")
        
        # Look for ItemList with crossword clues
        if item.get("@type") == "ItemList":
            items = item.get("itemListElement", [])
            list_name = item.get("name", "")
            
            if "Small" in list_name:
                for entry in items:
                    thing = entry.get("item", {})
                    if isinstance(thing, dict):
                        result["small"]["clues"].append({
                            "position": entry.get("position", 0),
                            "clue": thing.get("description", ""),
                            "answer": thing.get("name", ""),
                        })
            
            elif "Midsize" in list_name:
                for entry in items:
                    thing = entry.get("item", {})
                    if isinstance(thing, dict):
                        result["midsize"]["clues"].append({
                            "position": entry.get("position", 0),
                            "clue": thing.get("description", ""),
                            "answer": thing.get("name", ""),
                        })
    
    total = len(result["small"]["clues"]) + len(result["midsize"]["clues"])
    if total > 0:
        print(f"  Found: {len(result['small']['clues'])} Small + {len(result['midsize']['clues'])} Midsize = {total} clues")
        return result
    else:
        print(f"  No clues found for {date_str}")
        return None

def parse_password_page(date_str=None):
    """Parse today's password from codycrosssolutions.com."""
    url = "https://www.codycrosssolutions.com/codycross-password"
    print(f"  Fetching password: {url}")
    
    try:
        html = fetch_url(url)
    except Exception as e:
        print(f"  Error: {e}")
        return None
    
    # The password page has a simple format - extract answer text
    # Look for password patterns in the page
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Try to find the password answer
    # Common patterns on answer sites
    password_patterns = [
        r'(?:today[\'\s]s?\s+password(?:\s+answer)?(?:\s+is)?[:\s]+)([A-Z]{5,})',
        r'(?:password\s*(?:answer|solution)[:\s]+)([A-Z]{5,})',
        r'(?:the\s+word\s+is[:\s]+)([A-Z]{5,})',
    ]
    
    for pattern in password_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            password = match.group(1)
            print(f"  Found password: {password}")
            return {"date": date_str, "password": password}
    
    # Alternative: look for all-caps words that look like passwords (5+ letters)
    # Remove common non-password words
    all_caps = re.findall(r'\b([A-Z]{5,})\b', text)
    
    # Filter common words that aren't passwords
    skip = {"CODYCROSS", "TODAY", "PASSWORD", "ANSWER", "PUZZLE", "GAME", 
            "CROSSWORD", "AFTER", "BEFORE", "ABOUT", "ABOVE", "BELOW",
            "LEVEL", "WORLD", "GROUP", "HINTS", "CLICK", "CHECK"}
    
    candidates = [w for w in all_caps if w not in skip]
    if candidates:
        # The password is usually prominently displayed, so take the first candidate
        print(f"  Possible password candidates: {candidates[:5]}")
    
    return None

def load_existing_daily():
    """Load existing daily answers."""
    if os.path.exists(DAILY_FILE):
        try:
            with open(DAILY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"daily": [], "site": {}}

def save_daily(data):
    """Save daily answers to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    data["site"] = {
        "name": "CodyCross Daily Answers",
        "description": "Daily crossword (Small + Midsize) and password answers",
        "lastUpdated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "dataSource": "levelhacks.com + codycrosssolutions.com",
        "totalDays": len(data.get("daily", [])),
    }
    
    with open(DAILY_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  Saved to {DAILY_FILE}")

def main():
    print("=" * 60)
    print("  CodyCross Daily Games Scraper")
    print("=" * 60)
    
    # Parse arguments
    args = sys.argv[1:]
    dates = []
    fetch_password = False
    
    if "--week" in args:
        today = datetime.utcnow().date()
        for i in range(7):
            d = today - timedelta(days=i)
            dates.append(d.strftime("%Y-%m-%d"))
    elif "--password" in args:
        fetch_password = True
        today = datetime.utcnow().date().strftime("%Y-%m-%d")
        dates.append(today)
    elif args and args[0] != "--help":
        dates.append(args[0])
    else:
        dates.append(datetime.utcnow().date().strftime("%Y-%m-%d"))
    
    # Load existing data
    existing = load_existing_daily()
    existing_map = {}
    for d in existing.get("daily", []):
        existing_map[d["date"]] = d
    
    # Fetch crossword data for each date
    all_results = []
    for date_str in dates:
        print(f"\n--- {date_str} ---")
        
        if date_str in existing_map:
            print(f"  Already have data, skipping")
            all_results.append(existing_map[date_str])
            continue
        
        result = parse_daily_crossword(date_str)
        if result:
            all_results.append(result)
        
        # Small delay between requests
        import time
        time.sleep(1)
    
    # Also try password
    today_str = datetime.utcnow().date().strftime("%Y-%m-%d")
    password_data = parse_password_page(today_str)
    
    # Merge with existing
    for r in all_results:
        existing_map[r["date"]] = r
    
    all_sorted = sorted(existing_map.values(), key=lambda x: x["date"], reverse=True)
    
    output = {"daily": all_sorted}
    if password_data:
        output["password"] = password_data
    
    save_daily(output)
    
    # Summary
    total_small = sum(len(d.get("small", {}).get("clues", [])) for d in all_sorted)
    total_mid = sum(len(d.get("midsize", {}).get("clues", [])) for d in all_sorted)
    print(f"\n{'=' * 60}")
    print(f"  Done! {len(all_sorted)} days, {total_small} Small, {total_mid} Midsize clues")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
