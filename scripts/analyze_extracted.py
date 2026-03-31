#!/usr/bin/env python3
"""
CodyCross Extracted Data Analyzer
====================================
Run this AFTER extract_shizuku.sh to analyze the extracted files.
Finds player tokens, crossword bundles, and puzzle data.

Usage:
    python3 analyze_extracted.py /sdcard/Download/codycross_extracted/
"""
import os, sys, json, re, struct

def analyze_file(filepath, keywords):
    """Search a binary file for keywords and extract readable strings."""
    results = {}
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Check file type
        if data[:7] == b'UnityFS':
            results['type'] = 'Unity AssetBundle'
        elif data[:4] == b'RIFF':
            results['type'] = 'RIFF/WAV'
        elif data[:1] == b'{' or data[:1] == b'[':
            results['type'] = 'JSON'
            try:
                results['json'] = json.loads(data)
            except:
                results['type'] = 'Text'
        else:
            results['type'] = 'Binary'
        
        results['size'] = len(data)
        
        # Extract all readable strings (min 4 chars)
        all_strings = re.findall(rb'[\x20-\x7e]{4,}', data)
        results['string_count'] = len(all_strings)
        
        # Find keyword matches
        matches = []
        for s in all_strings:
            sl = s.lower()
            for kw in keywords:
                if kw.encode() in sl:
                    matches.append(s.decode('ascii', errors='ignore'))
                    break
        
        results['keyword_matches'] = matches
        return results
    except Exception as e:
        return {'error': str(e)}

def analyze_catalog(filepath):
    """Analyze a Unity Addressable catalog JSON."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        print(f"\n  Catalog type: {type(data).__name__}")
        if isinstance(data, dict):
            keys = list(data.keys())
            print(f"  Keys: {keys[:15]}")
            
            # Check for crossword/password references
            text = json.dumps(data)
            for kw in ['crossword', 'password', 'daily', 'tc', 'today', 'password']:
                count = text.lower().count(kw)
                if count > 0:
                    print(f"\n  *** '{kw}' found {count} times ***")
                    # Find context
                    idx = text.lower().find(kw)
                    ctx = text[max(0,idx-50):idx+100]
                    print(f"  Context: ...{ctx}...")
            
            # Check internal IDs
            internal_ids = data.get('m_InternalIds', [])
            if internal_ids:
                print(f"\n  Internal IDs: {len(internal_ids)}")
                for i, iid in enumerate(internal_ids):
                    iid_str = str(iid).lower()
                    if any(k in iid_str for k in ['crossword', 'password', 'daily', 'tc', 'content']):
                        print(f"    [{i}] MATCH: {iid}")
            
            # Check key data
            key_data = data.get('m_KeyDataString', '')
            if key_data:
                if '\x00' in key_data:
                    keys_list = key_data.split('\x00')
                    print(f"\n  Key data: {len(keys_list)} entries")
                    for k in keys_list:
                        if k.strip():
                            for kw in ['crossword', 'password', 'daily', 'tc', 'today']:
                                if kw in k.lower():
                                    print(f"    KEY: {k[:200]}")
        elif isinstance(data, list):
            print(f"  Array of {len(data)} items")
    except Exception as e:
        print(f"  Error: {e}")

def search_player_tokens(directory):
    """Search all files for player tokens and sessions."""
    print(f"\n{'='*60}")
    print("  SEARCHING FOR PLAYER TOKENS")
    print(f"{'='*60}")
    
    keywords = ['player', 'token', 'session', 'userid', 'google', 'facebook', 
                'uuid', 'auth', 'login', 'account']
    
    for root, dirs, files in os.walk(directory):
        for fname in files:
            fpath = os.path.join(root, fname)
            if os.path.getsize(fpath) > 50_000_000:  # Skip files > 50MB
                continue
            
            try:
                results = analyze_file(fpath, keywords)
                matches = results.get('keyword_matches', [])
                if matches:
                    short = os.path.relpath(fpath, directory)
                    print(f"\n  {short} ({results.get('size', 0):,} bytes)")
                    for m in matches[:15]:
                        print(f"    {m[:150]}")
            except:
                pass

def search_bundles(directory):
    """Search for crossword/password data in Unity bundles."""
    print(f"\n{'='*60}")
    print("  SEARCHING FOR CROSSWORD/PASSWORD BUNDLES")
    print(f"{'='*60}")
    
    keywords = ['crossword', 'password', 'clue', 'across', 'down', 'grid',
                'daily', 'today', 'tc_', 'cruzadinha', 'senha']
    
    for root, dirs, files in os.walk(directory):
        for fname in files:
            if fname.endswith(('.bundle', '.cody', '.asset', '.dat')):
                fpath = os.path.join(root, fname)
                if os.path.getsize(fpath) > 50_000_000:
                    continue
                
                try:
                    results = analyze_file(fpath, keywords)
                    matches = results.get('keyword_matches', [])
                    if matches:
                        short = os.path.relpath(fpath, directory)
                        print(f"\n  {short}")
                        print(f"    Type: {results.get('type', '?')}, Size: {results.get('size', 0):,}")
                        for m in matches[:20]:
                            print(f"    {m[:150]}")
                except:
                    pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_extracted.py /path/to/extracted/files")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not os.path.isdir(directory):
        print(f"Directory not found: {directory}")
        sys.exit(1)
    
    print(f"Analyzing: {directory}")
    
    # First check for catalog files
    print(f"\n{'='*60}")
    print("  CHECKING FOR ADDRESSABLE CATALOGS")
    print(f"{'='*60}")
    
    for root, dirs, files in os.walk(directory):
        for fname in files:
            if 'catalog' in fname.lower() and fname.endswith('.json'):
                fpath = os.path.join(root, fname)
                short = os.path.relpath(fpath, directory)
                print(f"\n  Found catalog: {short}")
                analyze_catalog(fpath)
    
    # Check for metadata
    print(f"\n{'='*60}")
    print("  CHECKING IL2CPP METADATA")
    print(f"{'='*60}")
    
    for root, dirs, files in os.walk(directory):
        for fname in files:
            if 'metadata' in fname.lower() or fname == 'global-metadata.dat':
                fpath = os.path.join(root, fname)
                short = os.path.relpath(fpath, directory)
                print(f"\n  Found metadata: {short}")
                results = analyze_file(fpath, [
                    'TodaysCrossword', 'TcDaily', 'TcYearMonth', 'TodaysPassword',
                    'CrosswordPuzzle', 'PasswordPuzzle', 'DailyPuzzle',
                    'PuzzleCrypto', 'PuzzleService', 'SyncContent',
                    'Addressable', 'LoadAsset', 'DownloadContent',
                ])
                if results.get('keyword_matches'):
                    print(f"  Size: {results.get('size', 0):,} bytes")
                    for m in results['keyword_matches']:
                        print(f"  {m[:150]}")
    
    # Search player tokens
    search_player_tokens(directory)
    
    # Search bundles
    search_bundles(directory)
    
    print(f"\n{'='*60}")
    print("  ANALYSIS COMPLETE")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
