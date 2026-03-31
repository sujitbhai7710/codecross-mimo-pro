#!/usr/bin/env python3
"""
CodyCross APK Extraction Script
=================================
Run this on your phone via Termux (rooted) or PC to extract
Daily Crossword and Password data from the APK.

WHERE THE DATA IS STORED:
=========================
The CodyCross APK (com.fanatee.cody) is split into multiple APKs:
  1. com.fanatee.cody.apk           - Main code + resources
  2. config.arm64_v8a.apk           - Native libs (libil2cpp.so)  
  3. UnityDataAssetPack.apk         - Maps + .cody encrypted puzzle files
  4. AddressablesAssetPack.apk      - Remote addressable bundles

DAILY CROSSWORD DATA:
  - Stored as Unity Addressable bundles in AddressablesAssetPack.apk
  - Loaded via key like 'tc_daily_en_2026_03_31' or similar
  - The local catalog (bundled in APK) maps keys -> bundle files
  - Bundles are encrypted .cody format

DAILY PASSWORD DATA:
  - Fetched from API: /TodaysPassword/Get (needs player token)
  - Player token stored in LiteDB at /data/data/com.fanatee.cody/files/

HOW TO USE:
===========
Option A: On rooted Android phone (Termux)
  1. Install CodyCross if not already installed
  2. Open Termux
  3. pkg update && pkg upgrade -y
  4. pkg install python git unzip -y
  5. su  (grant root)
  6. Copy this script to /sdcard/Download/
  7. python /sdcard/Download/extract_codycross.py

Option B: On PC
  1. Download APK from APKPure or similar
  2. Run this script with the APK path as argument:
     python extract_codycross.py /path/to/CodyCross.apk

Option C: On PC with split APK
  1. Download the XAPK from APKPure
  2. Extract the XAPK (it's a zip)
  3. Point this script to the extracted directory
"""

import os
import sys
import json
import zipfile
import struct
import re
from pathlib import Path

def find_apk_paths():
    """Find CodyCross APK on the device."""
    paths = [
        "/data/app/*/com.fanatee.cody*/base.apk",
        "/data/app/*/com.fanatee.cody*/split_config.arm64_v8a.apk",
        "/data/app/*/com.fanatee.cody*/split_UnityDataAssetPack.apk",
        "/data/app/*/com.fanatee.cody*/split_AddressablesAssetPack.apk",
        "/sdcard/Download/CodyCross*.apk",
        "/sdcard/Download/CodyCross*.xapk",
    ]
    import glob
    found = {}
    for pattern in paths:
        for f in glob.glob(pattern):
            name = os.path.basename(f)
            found[name] = f
    return found

def list_apk_contents(apk_path):
    """List all files inside an APK (zip)."""
    entries = []
    with zipfile.ZipFile(apk_path, 'r') as z:
        for info in z.infolist():
            entries.append({
                'name': info.filename,
                'size': info.file_size,
                'compressed': info.compress_size,
            })
    return entries

def extract_file(apk_path, file_path, output_dir):
    """Extract a specific file from an APK."""
    os.makedirs(output_dir, exist_ok=True)
    with zipfile.ZipFile(apk_path, 'r') as z:
        # Normalize the path
        for name in z.namelist():
            if file_path in name:
                z.extract(name, output_dir)
                return os.path.join(output_dir, name)
    return None

def extract_all_matching(apk_path, pattern, output_dir):
    """Extract all files matching a pattern from an APK."""
    os.makedirs(output_dir, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(apk_path, 'r') as z:
        for name in z.namelist():
            if re.search(pattern, name, re.IGNORECASE):
                out_path = os.path.join(output_dir, os.path.basename(name))
                # Flatten the path
                with z.open(name) as src, open(out_path, 'wb') as dst:
                    dst.write(src.read())
                extracted.append(out_path)
    return extracted

def search_binary_for_strings(filepath, keywords, min_length=4):
    """Search a binary file for readable strings containing keywords."""
    found = []
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Extract readable strings (ASCII, min 4 chars)
        strings = re.findall(rb'[\x20-\x7e]{4,}', data)
        
        for s in strings:
            s_lower = s.lower()
            for kw in keywords:
                if kw.encode() in s_lower:
                    found.append(s.decode('ascii', errors='ignore'))
                    break
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return found

def analyze_bundle(filepath):
    """Quick analysis of a Unity AssetBundle file."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(32)
        
        if header[:7] == b'UnityFS':
            version = struct.unpack('<I', header[8:12])[0]
            print(f"  Unity AssetBundle v{version}")
            print(f"  File size: {os.path.getsize(filepath)} bytes")
            
            # Search for readable strings
            keywords = ["crossword", "password", "clue", "answer", "puzzle", 
                        "tc_", "daily", "today", "grupo", "fase", "cifra",
                        "dica", "resposta", "cruzadinha", "senha"]
            strings = search_binary_for_strings(filepath, keywords, min_length=6)
            if strings:
                print(f"  Found {len(strings)} matching strings:")
                for s in strings[:30]:
                    print(f"    {s[:120]}")
            else:
                print(f"  No matching strings found (file may be compressed/encrypted)")
        elif header[:4] == b'RIFF':
            print(f"  RIFF/WAV audio file ({os.path.getsize(filepath)} bytes)")
        else:
            print(f"  Unknown format. Header: {header[:20].hex()}")
            # Try to find strings anyway
            keywords = ["crossword", "password", "clue", "answer"]
            strings = search_binary_for_strings(filepath, keywords, min_length=6)
            if strings:
                print(f"  But found {len(strings)} matching strings:")
                for s in strings[:20]:
                    print(f"    {s[:120]}")
    except Exception as e:
        print(f"  Error: {e}")

def analyze_metadata(apk_path):
    """Analyze IL2CPP metadata for crossword-related classes."""
    print("\n" + "=" * 70)
    print("  STEP 3: Analyzing IL2CPP Metadata")
    print("=" * 70)
    
    # Extract global-metadata.dat
    output_dir = "/sdcard/Download/codycross_extracted"
    os.makedirs(output_dir, exist_ok=True)
    
    meta_path = extract_file(apk_path, "global-metadata.dat", output_dir)
    if meta_path:
        print(f"  Extracted: {meta_path}")
        keywords = [
            "TodaysCrossword", "TcDaily", "TcYearMonth", "TodaysPassword",
            "CrosswordPuzzle", "PasswordPuzzle", "DailyPuzzle",
            "PuzzleCrypto", "PuzzleService", "ContentSync",
            "Addressable", "AssetBundle", "LoadAsset",
            "SyncContent", "DownloadContent", "GetContent",
        ]
        strings = search_binary_for_strings(meta_path, keywords, min_length=8)
        if strings:
            print(f"\n  Found {len(strings)} class/method references:")
            for s in strings[:50]:
                print(f"    {s[:150]}")
    else:
        print("  global-metadata.dat not found in this APK")
        print("  It might be in a different split APK")

def analyze_addressable_catalog(apk_path, output_dir):
    """Find and analyze the bundled Addressable catalog."""
    print("\n" + "=" * 70)
    print("  STEP 4: Searching for bundled Addressable catalogs")
    print("=" * 70)
    
    catalog_patterns = [
        r'catalog.*\.json$',
        r'catalog.*\.hash$',
        r'catalog.*\.bundle$',
        r'addressable.*catalog',
        r'content.*catalog',
    ]
    
    for pattern in catalog_patterns:
        files = extract_all_matching(apk_path, pattern, output_dir + "/catalogs")
        if files:
            print(f"\n  Pattern '{pattern}' matched {len(files)} files:")
            for f in files:
                print(f"    {f} ({os.path.getsize(f)} bytes)")
                try:
                    with open(f, 'rb') as fh:
                        data = fh.read(100)
                    if data[:1] == b'{':
                        print(f"    -> JSON catalog!")
                    elif data[:7] == b'UnityFS':
                        print(f"    -> Unity AssetBundle catalog!")
                    else:
                        print(f"    -> Format: {data[:20].hex()}")
                except:
                    pass

def analyze_cody_files(apk_path, output_dir):
    """Find and analyze .cody encrypted puzzle files."""
    print("\n" + "=" * 70)
    print("  STEP 5: Analyzing .cody puzzle files")
    print("=" * 70)
    
    cody_files = extract_all_matching(apk_path, r'\.cody$', output_dir + "/cody_files")
    
    if not cody_files:
        print("  No .cody files found in this APK")
        print("  They might be in UnityDataAssetPack.apk")
        return
    
    print(f"\n  Found {len(cody_files)} .cody files:")
    for f in sorted(cody_files):
        size = os.path.getsize(f)
        print(f"  {os.path.basename(f):40s} {size:>10,} bytes")
        
        # Check if it's a Unity bundle
        with open(f, 'rb') as fh:
            header = fh.read(20)
        if header[:7] == b'UnityFS':
            # Search for crossword/password strings
            keywords = ["crossword", "password", "daily", "tc", "today"]
            strings = search_binary_for_strings(f, keywords, min_length=6)
            if strings:
                print(f"    *** Contains crossword/password references! ***")
                for s in strings[:10]:
                    print(f"      {s[:120]}")
    
    # Try to find any that might contain crossword data
    print(f"\n  Searching ALL .cody files for crossword/password keywords...")
    for f in cody_files:
        keywords = ["crossword", "cruzadinha", "password", "senha", "daily", "todays"]
        strings = search_binary_for_strings(f, keywords, min_length=8)
        if strings:
            print(f"\n  *** {os.path.basename(f)} HAS CROSSWORD/PASSWORD DATA ***")
            for s in strings[:20]:
                print(f"    {s[:150]}")

def find_player_data():
    """Find player session data from the game's storage."""
    print("\n" + "=" * 70)
    print("  STEP 6: Looking for Player Data (session/token)")
    print("=" * 70)
    
    game_dir = "/data/data/com.fanatee.cody"
    
    # Check if we have root access
    if not os.path.exists(game_dir):
        print(f"  Cannot access {game_dir}")
        print(f"  You need ROOT access to read game data")
        print(f"  Run: su")
        return
    
    # Check SharedPreferences
    prefs_dir = os.path.join(game_dir, "shared_prefs")
    if os.path.exists(prefs_dir):
        print(f"\n  Found shared_prefs:")
        for f in os.listdir(prefs_dir):
            filepath = os.path.join(prefs_dir, f)
            try:
                with open(filepath, 'r') as fh:
                    content = fh.read()
                keywords = ["player", "token", "session", "userid", "google", "facebook"]
                matches = []
                for line in content.split("\n"):
                    for kw in keywords:
                        if kw in line.lower():
                            matches.append(line.strip())
                            break
                if matches:
                    print(f"\n  {f}:")
                    for m in matches[:10]:
                        print(f"    {m[:150]}")
            except:
                pass
    
    # Check files directory
    files_dir = os.path.join(game_dir, "files")
    if os.path.exists(files_dir):
        print(f"\n  Files in {files_dir}:")
        for f in sorted(os.listdir(files_dir)):
            fpath = os.path.join(files_dir, f)
            size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
            print(f"    {f:40s} {size:>10,} bytes")
    
    # Check databases
    db_dir = os.path.join(game_dir, "databases")
    if os.path.exists(db_dir):
        print(f"\n  Databases:")
        for f in sorted(os.listdir(db_dir)):
            print(f"    {f}")

def main():
    print("=" * 70)
    print("  CodyCross APK Data Extractor")
    print("  Looking for Daily Crossword & Password data")
    print("=" * 70)
    
    output_dir = "/sdcard/Download/codycross_extracted"
    
    # Check for APK argument or find on device
    if len(sys.argv) > 1:
        apk_path = sys.argv[1]
    else:
        print("\n  Scanning for CodyCross APK on device...")
        found = find_apk_paths()
        if found:
            print(f"  Found {len(found)} APK files:")
            for name, path in found.items():
                print(f"    {name}: {path}")
            
            # Use the main APK or first found
            if "base.apk" in found:
                apk_path = found["base.apk"]
            elif "split_AddressablesAssetPack.apk" in found:
                apk_path = found["split_AddressablesAssetPack.apk"]
            else:
                apk_path = list(found.values())[0]
        else:
            print("\n  No CodyCross APK found on device!")
            print("  Usage: python extract_codycross.py /path/to/apk")
            print("  Or download the XAPK and extract it first")
            return
    
    print(f"\n  Using APK: {apk_path}")
    print(f"  Size: {os.path.getsize(apk_path):,} bytes")
    
    # Step 1: List all contents
    print("\n" + "=" * 70)
    print("  STEP 1: Listing APK contents")
    print("=" * 70)
    
    entries = list_apk_contents(apk_path)
    print(f"  Total files: {len(entries)}")
    
    # Find interesting files
    interesting = []
    for e in entries:
        name = e['name'].lower()
        if any(k in name for k in ['.cody', 'catalog', 'addressable', 'metadata', 
                                     'crossword', 'password', 'global-metadata',
                                     'libil2cpp', '.json', 'config']):
            interesting.append(e)
    
    print(f"\n  Interesting files ({len(interesting)}):")
    for e in sorted(interesting, key=lambda x: x['name'])[:50]:
        print(f"    {e['name']:60s} {e['size']:>10,} bytes")
    
    # Step 2: Look for crossword/password related files
    print("\n" + "=" * 70)
    print("  STEP 2: Searching for crossword/password content")
    print("=" * 70)
    
    cw_patterns = [
        r'crossword', r'password', r'daily', r'tc_', r'today',
        r'cruzadinha', r'senha', r'event',
    ]
    
    for pattern in cw_patterns:
        files = extract_all_matching(apk_path, pattern, output_dir + "/content")
        if files:
            print(f"\n  Pattern '{pattern}' matched {len(files)} files:")
            for f in files:
                print(f"    {f} ({os.path.getsize(f)} bytes)")
                analyze_bundle(f)
    
    # Step 3: Analyze metadata
    analyze_metadata(apk_path)
    
    # Step 4: Find addressable catalogs
    analyze_addressable_catalog(apk_path, output_dir)
    
    # Step 5: Analyze .cody files
    analyze_cody_files(apk_path, output_dir)
    
    # Step 6: Look for player data (if rooted)
    find_player_data()
    
    # Summary
    print("\n" + "=" * 70)
    print("  EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"  All extracted files saved to: {output_dir}")
    print(f"\n  NEXT STEPS:")
    print(f"  1. Check {output_dir}/content/ for crossword/password bundles")
    print(f"  2. Check {output_dir}/catalogs/ for addressable catalog files")
    print(f"  3. Check {output_dir}/cody_files/ for .cody puzzle files")
    print(f"  4. For player token: run with root access (su)")
    print(f"  5. Upload extracted catalog JSON for further analysis")

if __name__ == "__main__":
    main()
