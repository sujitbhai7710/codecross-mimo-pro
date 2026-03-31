# CodyCross Shizuku Extractor - Setup Guide
# ==============================================
# Complete guide for setting up on a NON-ROOTED phone
# using Termux + Shizuku + Wireless Debugging

========================================
PHONE SETUP (One-Time)
========================================

STEP 1: Install Required Apps
------------------------------
1. Install Termux from F-Droid (NOT Play Store)
   - Download: https://f-droid.org/en/packages/com.termux/
   - IMPORTANT: Use F-Droid version, Play Store version is outdated

2. Install Shizuku from Play Store or GitHub
   - Play Store: search "Shizuku"
   - GitHub: https://github.com/RikkaApps/Shizuku/releases

3. Make sure CodyCross is installed and you've opened it at least once


STEP 2: Enable Developer Options & Wireless Debugging
------------------------------------------------------
1. Go to Settings > About Phone
2. Tap "Build number" 7 times (enables Developer Options)
3. Go to Settings > Developer Options (or System > Developer Options)
4. Turn ON "Developer Options"
5. Turn ON "Wireless Debugging"


STEP 3: Start Shizuku
----------------------
1. Open the Shizuku app
2. Tap "Start via Wireless Debugging"
3. If it asks you to pair:
   - Go to Settings > Developer Options > Wireless Debugging
   - Tap "Pair device with pairing code"
   - Note the IP:PORT (e.g., 192.168.1.5:37891) and the 6-digit code
   - Go back to Shizuku and enter them
4. After pairing, Shizuku should say "Shizuku is running"
5. You should see a Shizuku notification in your notification bar


========================================
TERMUX SETUP (One-Time)
========================================

Open Termux and run these commands one by one:

# Update Termux packages
pkg update && pkg upgrade -y

# Install required packages
pkg install python git termux-api android-tools -y

# Install Python dependencies
pip install requests

# Create project folder
mkdir -p ~/codycross


========================================
FILE PLACEMENT ON PHONE
========================================

Your phone folder structure should look like this:

~/codycross/                          <-- Main folder (create with mkdir)
├── shizuku_extract.sh                <-- Main extraction script (STEP A)
├── fetch_daily_api.py                <-- Python API fetcher (STEP B)
├── extracted/                        <-- Created automatically by script
│   ├── player_token.json             <-- Your extracted token (auto-generated)
│   ├── shared_prefs/                 <-- Raw preference files (auto-generated)
│   │   ├── com.fanatee.cody_preferences.xml
│   │   └── ...
│   └── bundles/                      <-- Pulled .cody files (auto-generated)
└── daily_data/                       <-- Created by Python script
    ├── password_20260401_120000.json
    ├── crossword_20260401_120000.json
    └── endpoints_20260401_120000.json


WHERE TO PUT THE FILES:
-----------------------

File 1: shizuku_extract.sh
  Path on phone: ~/codycross/shizuku_extract.sh
  How to create: Copy the content from the repo file and paste it
  
  In Termux:
    cd ~/codycross
    nano shizuku_extract.sh
    # Paste the script content
    # Press Ctrl+X, then Y, then Enter to save
    chmod +x shizuku_extract.sh

File 2: fetch_daily_api.py
  Path on phone: ~/codycross/fetch_daily_api.py
  How to create: Same as above
  
  In Termux:
    cd ~/codycross
    nano fetch_daily_api.py
    # Paste the Python script content
    # Press Ctrl+X, then Y, then Enter to save


ALTERNATIVE: Transfer files from computer
------------------------------------------
If you have the files on a computer:

Option A: Via USB (with Shizuku wireless debugging on)
  1. Make sure phone and computer are on same WiFi
  2. In Termux: pkg install openssh
  3. In Termux: sshd   (starts SSH server)
  4. On computer: scp shizuku_extract.sh user@PHONE_IP:~/codycross/
  5. On computer: scp fetch_daily_api.py user@PHONE_IP:~/codycross/

Option B: Via Git
  1. In Termux: cd ~/codycross
  2. In Termux: git init
  3. Push files from computer, then pull on phone
  4. In Termux: git pull

Option C: Via curl from GitHub raw
  1. Upload files to your GitHub repo
  2. In Termux: cd ~/codycross
  3. In Termux: curl -LO https://raw.githubusercontent.com/YOUR_USER/codecross-mimo-pro/main/scripts/shizuku_extract.sh
  4. In Termux: curl -LO https://raw.githubusercontent.com/YOUR_USER/codecross-mimo-pro/main/fetcher/fetch_daily_api.py


========================================
HOW TO RUN (Every Time)
========================================

STEP A: Extract Player Token
-----------------------------
1. Make sure Shizuku is running (check notification bar)
2. Make sure CodyCross is installed and you've played at least one level
3. Open Termux

4. Run the extraction:
   cd ~/codycross
   ./shizuku_extract.sh

5. The script will:
   - Connect to Shizuku
   - Access CodyCross app data
   - Extract player token, player ID, device ID
   - Copy shared_prefs files
   - Copy .cody bundle files (if any)
   - Save everything to ~/codycross/extracted/

6. If it says "Token: NOT FOUND":
   - Open CodyCross and play a level first
   - Make sure you're logged in (Google or Facebook)
   - Run the script again
   - Or check ~/codycross/extracted/shared_prefs/ manually


STEP B: Fetch Daily Answers
-----------------------------
1. After extraction is done (Step A succeeded)

2. Run the Python fetcher:
   cd ~/codycross
   python3 fetch_daily_api.py

3. The script will:
   - Read your player token from extracted/player_token.json
   - Try multiple API endpoints for daily password
   - Try multiple API endpoints for daily crossword
   - Explore all authenticated endpoints
   - Save results to ~/codycross/daily_data/

4. Optional flags:
   python3 fetch_daily_api.py --explore-only    # Only test endpoints
   python3 fetch_daily_api.py --dev             # Also try dev API
   python3 fetch_daily_api.py --token "ABC" --player-id "123"  # Manual token

5. Results will be in:
   ~/codycross/daily_data/
   ├── password_TIMESTAMP.json      # Daily password data
   ├── crossword_TIMESTAMP.json     # Daily crossword data
   └── endpoints_TIMESTAMP.json     # All discovered endpoints


========================================
TROUBLESHOOTING
========================================

PROBLEM: "Cannot connect to Shizuku!"
FIX:
  1. Open Shizuku app
  2. Stop and restart Shizuku
  3. Make sure Wireless Debugging is ON in Developer Options
  4. In Shizuku: Menu > Check "Start on boot" (for convenience)
  5. Try running the script again

PROBLEM: "CodyCross NOT found!"
FIX:
  1. Install CodyCross from Play Store
  2. Open it once so it creates data files
  3. Run the script again

PROBLEM: "Cannot access app data directory!"
FIX:
  1. Make sure Shizuku shows "is running" with notification
  2. In Shizuku: Menu > "Manage shell permission"
  3. Grant permission to Termux
  4. Or try: In Shizuku > Menu > "Authorize for specific app" > Termux

PROBLEM: "No player token found!"
FIX:
  1. Open CodyCross
  2. Sign in with Google or Facebook account
  3. Play any level / open daily crossword
  4. Go back to Termux and run shizuku_extract.sh again
  5. Check ~/codycross/extracted/shared_prefs/ manually:
     - Look for files with "player" or "auth" in name
     - Open them and search for long strings near "token" or "auth"

PROBLEM: "API returns Ok:false, Status:1"
FIX:
  - This means the token is wrong or expired
  - Try playing a fresh level in CodyCross
  - Re-run shizuku_extract.sh to get fresh token
  - Check if the token looks complete (not truncated)

PROBLEM: "No working daily endpoints found"
FIX:
  - The daily crossword data may be in .cody bundle files
  - Check ~/codycross/extracted/bundles/ for files
  - The crossword data is encrypted Unity addressable assets
  - You may need the AES key (from Frida extraction) to decrypt them
  - Password endpoint should work if token is valid

PROBLEM: "adb: command not found"
FIX:
  pkg install android-tools -y

PROBLEM: "python3: command not found"
FIX:
  pkg install python -y

PROBLEM: "permission denied" when running shizuku_extract.sh
FIX:
  chmod +x ~/codycross/shizuku_extract.sh


========================================
QUICK REFERENCE
========================================

# First time setup
pkg update -y && pkg install python git termux-api android-tools -y
pip install requests
mkdir -p ~/codycross
# Then copy the two files to ~/codycross/

# Extract token
cd ~/codycross && ./shizuku_extract.sh

# Fetch daily data
cd ~/codycross && python3 fetch_daily_api.py

# Fetch with extra options
cd ~/codycross && python3 fetch_daily_api.py --dev --explore-only

# Check results
ls ~/codycross/daily_data/
cat ~/codycross/extracted/player_token.json
