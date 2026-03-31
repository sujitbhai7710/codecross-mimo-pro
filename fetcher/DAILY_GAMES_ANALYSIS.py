#!/usr/bin/env python3
"""
CodyCross Daily Games API Analysis & Player Auth Guide
======================================================

SUMMARY OF FINDINGS:
====================

1. DAILY PASSWORD GAME:
   - Endpoint: /TodaysPassword/Get (EXISTS on both DEV and PROD)
   - Status: Returns {"Ok":false,"Status":1} — NEEDS PLAYER TOKEN
   - The endpoint validates but fails without authentication
   - DEV gives detailed error: System.NullReferenceException (needs player context)

2. DAILY CROSSWORD:
   - NO endpoint found on game.codycross-game.com
   - NO endpoint found on codydev.fulano.com.br
   - Only asset found: headers-remote_assets_header-crosswords.bundle (UI image only)
   - The crossword data likely comes from a DIFFERENT mechanism:
     a) Dynamically constructed CDN URLs (not in static catalog)
     b) Internal game content that's pre-bundled in the APK
     c) A separate API domain entirely

3. PLAYER AUTHENTICATION:
   - /Player/Login EXISTS but always returns Ok:false (Status:1)
   - Needs: Google Sign-In token OR Facebook auth token OR device identifier
   - Once logged in, player gets a session token
   - This token is needed for TodaysPassword/Get and probably crossword

4. WORKING ENDPOINTS (no auth needed):
   - /Config/Get -> Full game config ✅
   - /Puzzle/GetMundo -> Main game puzzle data (all worlds) ✅

5. ENDPOINTS THAT EXIST BUT NEED AUTH:
   - /TodaysPassword/Get (GET or POST) -> Daily password puzzle
   - /Player/Login (POST) -> Player authentication
   - /Player/GetPuzzleSettings (GET) -> Player puzzle settings
   - /Player/GetAlgoritmoDePropagacao (GET) -> Propagation algorithm

TERMUX PLAYER ID EXTRACTION GUIDE:
===================================

The game (com.fanatee.cody) stores player data using LiteDB (embedded NoSQL).
The player session/token can be extracted from the game's data directory.

PREREQUISITES:
- Rooted Android phone with CodyCross installed
- Termux app installed

STEP 1: Get the player data file
```bash
# In Termux
pkg update && pkg upgrade -y
pkg install root-repo
pkg install tsu

# Grant root and navigate to game data
tsu
cd /data/data/com.fanatee.cody/

# List files
ls -la
ls -la files/
ls -la shared_prefs/
```

STEP 2: Check SharedPreferences for player ID
```bash
tsu
cd /data/data/com.fanatee.cody/shared_prefs/
cat *.xml | grep -i "player\|token\|session\|userid\|google\|facebook"
```

STEP 3: Check LiteDB for player session
```bash
tsu
cd /data/data/com.fanatee.cody/files/

# Look for LiteDB or database files
find . -name "*.db" -o -name "*lite*" -o -name "*player*" -o -name "*session*"

# If LiteDB.db exists, extract strings
strings ./LiteDB.db | grep -i "player\|token\|session" | head -50

# Or use xxd for binary inspection
xxd LiteDB.db | grep -i "player\|token"
```

STEP 4: Copy to accessible location for analysis
```bash
tsu
cp /data/data/com.fanatee.cody/files/LiteDB.db /sdcard/Download/codycross_db.db
chmod 644 /sdcard/Download/codycross_db.db
```

STEP 5: Network capture (alternative method)
```bash
# In Termux (rooted)
pkg install tcpdump
tsu
tcpdump -i any -A -s 0 'host game.codycross-game.com' > /sdcard/Download/codycross_capture.txt &

# Then open CodyCross and play a puzzle
# After a minute, check the capture:
grep -i "player\|token\|login\|password\|crossword" /sdcard/Download/codycross_capture.txt
```

STEP 6: Monitor API calls with mitmproxy (best method)
```bash
# Install mitmproxy
pip install mitmproxy

# Start proxy
mitmproxy --mode transparent --listen-port 8080

# On rooted phone, redirect traffic:
iptables -t nat -A OUTPUT -p tcp --dport 443 -j DNAT --to-destination 127.0.0.1:8080
iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination 127.0.0.1:8080

# Open CodyCross - you'll see ALL API calls including player auth
```

WHAT TO LOOK FOR:
- Player UUID (e.g., "a1b2c3d4-...")
- Session token (e.g., "eyJhbGciOi...")
- Google Play Games ID
- Facebook access token

Once you have the player token, use it like:
```python
params = {
    "languageId": "1aca585a-8e15-3029-89a0-54aa078acec2",
    "appToken": "872fbb4c-fa3c-4534-b6e4-4b56bd7d3fc6",
    "country": "US",
    "deviceType": "Android",
    "appVersion": "1.0.0",
    "playerToken": "YOUR_PLAYER_TOKEN_HERE",
}
r = requests.get("https://game.codycross-game.com/TodaysPassword/Get", params=params)
```
"""

import sys
print(__doc__)
