#!/bin/bash
# ============================================================
# CodyCross Data Extractor - Shizuku (Non-Rooted Phone)
# ============================================================
# Works on NON-ROOTED phones using Shizuku + Wireless Debugging
# Extracts: Player Token, Player ID, App Config, .cody bundles
#
# PREREQUISITES (on your phone):
#   1. Shizuku app installed + started (using wireless debugging)
#   2. Termux installed (from F-Droid)
#   3. CodyCross game installed and opened at least once
#   4. Termux: pkg install python git termux-api android-tools
#
# USAGE:
#   chmod +x shizuku_extract.sh
#   ./shizuku_extract.sh
#
# FILE PLACEMENT:
#   Put this file in: ~/codycross/shizuku_extract.sh
#   Also put fetch_daily_api.py in the same folder
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Paths
BASE_DIR="$HOME/codycross"
EXTRACT_DIR="$BASE_DIR/extracted"
BUNDLE_DIR="$EXTRACT_DIR/bundles"
PREFS_DIR="$EXTRACT_DIR/shared_prefs"
OUTPUT_FILE="$EXTRACT_DIR/player_token.json"
ADB_PAIR_LOG="$BASE_DIR/.adb_paired"

CODYCROSS_PKG="com.fanatee.cody"
CODYCROSS_DATA="/data/data/$CODYCROSS_PKG"

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  CodyCross Shizuku Extractor${NC}"
echo -e "${BLUE}  (Non-Rooted Phone)${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e ""

# ============================================================
# STEP 0: Setup directories
# ============================================================
echo -e "${YELLOW}[0] Setting up directories...${NC}"
mkdir -p "$BASE_DIR" "$EXTRACT_DIR" "$BUNDLE_DIR" "$PREFS_DIR"
echo -e "  ${GREEN}Done${NC}: $BASE_DIR/"

# ============================================================
# STEP 1: Pair ADB with Wireless Debugging
# ============================================================
echo -e "\n${YELLOW}[1] Checking ADB connection...${NC}"

# Check if adb is installed
if ! command -v adb &> /dev/null 2>&1; then
    echo -e "${RED}ERROR: adb not found. Run: pkg install android-tools${NC}"
    exit 1
fi

# Kill any stale ADB server
adb kill-server 2>/dev/null || true
sleep 1
adb start-server 2>/dev/null || true

# Check if any device is already connected
CONNECTED=$(adb devices 2>/dev/null | grep -v "List" | grep -v "^$" | grep -v "daemon" | head -1 || true)

if [ -z "$CONNECTED" ]; then
    # Check if we paired before (cached)
    if [ -f "$ADB_PAIR_LOG" ]; then
        CACHED_ADDR=$(cat "$ADB_PAIR_LOG" 2>/dev/null)
        if [ -n "$CACHED_ADDR" ]; then
            echo -e "  Reconnecting to $CACHED_ADDR..."
            adb connect "$CACHED_ADDR" 2>/dev/null || true
            sleep 1
            CONNECTED=$(adb devices 2>/dev/null | grep -v "List" | grep -v "^$" | grep -v "daemon" | head -1 || true)
        fi
    fi
fi

if [ -z "$CONNECTED" ]; then
    echo -e "\n${RED}==========================================${NC}"
    echo -e "${RED}  No ADB device connected!${NC}"
    echo -e "${RED}==========================================${NC}"
    echo -e ""
    echo -e "${YELLOW}You need to pair ADB with your phone's Wireless Debugging.${NC}"
    echo -e ""
    echo -e "${CYAN}=== STEP-BY-STEP INSTRUCTIONS ===${NC}"
    echo -e ""
    echo -e "  1. Go to phone: ${BLUE}Settings > Developer Options${NC}"
    echo -e "  2. Scroll down and turn ON ${BLUE}Wireless Debugging${NC}"
    echo -e "  3. You'll see something like:"
    echo -e "     ${CYAN}IP address & port: 127.0.0.1:ABCDE${NC}"
    echo -e "     (note the PORT number after the colon)"
    echo -e ""
    echo -e "  4. Tap ${BLUE}'Pair device with pairing code'${NC}"
    echo -e "     You'll see a DIFFERENT port and a 6-digit code"
    echo -e "     (e.g., Wi-Fi pairing port: 123456, code: 789012)"
    echo -e ""
    echo -e "  5. Now come to Termux and type:"
    echo -e "     ${GREEN}adb pair 127.0.0.1:PAIRING_PORT${NC}"
    echo -e "     It will ask for the code - enter the 6-digit number"
    echo -e ""
    echo -e "  6. After pairing succeeds, type:"
    echo -e "     ${GREEN}adb connect 127.0.0.1:MAIN_PORT${NC}"
    echo -e "     (the MAIN port from step 3, not the pairing port)"
    echo -e ""
    echo -e "  7. Type ${GREEN}adb devices${NC} to verify. You should see a device."
    echo -e ""
    echo -e "  8. Then run this script again: ${GREEN}./shizuku_extract.sh${NC}"
    echo -e ""
    echo -e "${CYAN}=== EXAMPLE ===${NC}"
    echo -e "  If wireless debugging shows port ${CYAN}37891${NC}"
    echo -e "  and pairing shows port ${CYAN}33719${NC} with code ${CYAN}482910${NC}:"
    echo -e ""
    echo -e "  ${GREEN}adb pair 127.0.0.1:33719${NC}"
    echo -e "  Enter pairing code: ${CYAN}482910${NC}"
    echo -e "  ${GREEN}adb connect 127.0.0.1:37891${NC}"
    echo -e "  ${GREEN}adb devices${NC}"
    echo -e ""
    echo -e "${YELLOW}NOTE: Shizuku must be running too!${NC}"
    echo -e "  Open Shizuku app > tap 'Start via Wireless Debugging'"
    echo -e "  Shizuku uses the same wireless debugging connection."
    echo -e "  Once paired, Shizuku handles the elevated permissions."
    echo -e ""
    exit 1
fi

# We have a connection!
DEVICE_ID=$(echo "$CONNECTED" | awk '{print $1}')
DEVICE_STATE=$(echo "$CONNECTED" | awk '{print $2}')
echo -e "  ${GREEN}Connected${NC}: $DEVICE_ID ($DEVICE_STATE)"

# Cache the connection
echo "$DEVICE_ID" > "$ADB_PAIR_LOG"

# ============================================================
# STEP 2: Test elevated shell access
# ============================================================
echo -e "\n${YELLOW}[2] Testing shell access...${NC}"

# Test if we can list app data (this requires elevated/shell permissions)
TEST_LS=$(adb shell "ls $CODYCROSS_DATA/shared_prefs/ 2>&1" | head -5)

if echo "$TEST_LS" | grep -qi "permission denied\|No such file\|error"; then
    echo -e "  ${YELLOW}Standard ADB shell access denied (expected for /data/data/)"
    echo -e "  This means Shizuku's elevated shell is needed.${NC}"
    
    # Try Shizuku's elevated shell methods
    echo -e "  ${CYAN}Trying Shizuku elevated methods...${NC}"
    
    ELEVATED_WORKS=false
    
    # Method A: Check if Shizuku provides shell via its service
    # Shizuku v13+ intercepts adb shell commands when it's running
    # The key is that Shizuku replaces adbd with its own
    
    # Try running as root through Shizuku
    ROOT_TEST=$(adb shell "id" 2>/dev/null | tr -d '\r')
    echo -e "  Shell UID: $ROOT_TEST"
    
    if echo "$ROOT_TEST" | grep -q "uid=0\|uid=2000"; then
        ELEVATED_WORKS=true
        echo -e "  ${GREEN}Elevated shell confirmed!${NC}"
    else
        echo -e "  ${YELLOW}Shell is running as unprivileged user${NC}"
        echo -e ""
        echo -e "  ${RED}Shizuku elevated shell is not active.${NC}"
        echo -e ""
        echo -e "  ${CYAN}Fix steps:${NC}"
        echo -e "  1. Open ${BLUE}Shizuku${NC} app"
        echo -e "  2. Make sure it says ${GREEN}'Shizuku is running'${NC}"
        echo -e "  3. In Shizuku: tap the 3-dot menu"
        echo -e "  4. Tap ${BLUE}'Manage app shell permission'${NC}"
        echo -e "  5. Find and enable ${BLUE}Termux${NC}"
        echo -e "  6. Run this script again"
        echo -e ""
        echo -e "  ${CYAN}Alternative: Check Shizuku's notification${NC}"
        echo -e "  - Pull down notification shade"
        echo -e "  - Shizuku should show 'Shizuku is running'"
        echo -e "  - If not, open Shizuku and tap Start"
        echo -e ""
        exit 1
    fi
else
    echo -e "  ${GREEN}Shell access works!${NC}"
    ELEVATED_WORKS=true
fi

# Helper: run adb shell command
run_adb() {
    adb shell "$1" 2>/dev/null | tr -d '\r'
}

# ============================================================
# STEP 3: Verify CodyCross is installed
# ============================================================
echo -e "\n${YELLOW}[3] Checking CodyCross installation...${NC}"

CODYCROSS_CHECK=$(run_adb "pm list packages 2>/dev/null | grep $CODYCROSS_PKG")
if [ -z "$CODYCROSS_CHECK" ]; then
    echo -e "  ${RED}CodyCross NOT found! Install it from Play Store first.${NC}"
    exit 1
fi

CODYCROSS_VER=$(run_adb "dumpsys package $CODYCROSS_PKG 2>/dev/null | grep versionName" | head -1 | grep -oP 'versionName=\K[^\s]+' || echo "unknown")
echo -e "  ${GREEN}Found${NC}: $CODYCROSS_PKG (v$CODYCROSS_VER)"

# Verify we can list app data
DATA_LIST=$(run_adb "ls $CODYCROSS_DATA/ 2>&1" | head -10)
if echo "$DATA_LIST" | grep -qi "permission denied"; then
    echo -e "  ${RED}Cannot access $CODYCROSS_DATA/ - permission denied${NC}"
    echo -e "  Shizuku elevated shell is required. See step 2 instructions."
    exit 1
fi
echo -e "  ${GREEN}App data accessible${NC}:"
echo "$DATA_LIST" | head -5 | while read line; do
    [ -n "$line" ] && echo -e "    $line"
done

# ============================================================
# STEP 4: Extract SharedPreferences
# ============================================================
echo -e "\n${YELLOW}[4] Extracting SharedPreferences...${NC}"

PREFS_LIST=$(run_adb "ls $CODYCROSS_DATA/shared_prefs/ 2>/dev/null" || true)
PREFS_COUNT=$(echo "$PREFS_LIST" | grep -c '.' || echo 0)
echo -e "  Found $PREFS_COUNT pref files"

PLAYER_TOKEN=""
PLAYER_ID=""
PLAYER_NAME=""
DEVICE_ID_VAL=""

for pref_file in $PREFS_LIST; do
    [ -z "$pref_file" ] && continue
    
    # Pull the pref file content
    PREF_CONTENT=$(run_adb "cat '$CODYCROSS_DATA/shared_prefs/$pref_file'" 2>/dev/null || true)
    if [ -z "$PREF_CONTENT" ]; then
        continue
    fi
    
    # Save raw content
    echo "$PREF_CONTENT" > "$PREFS_DIR/$pref_file"
    
    # Extract player token (try many possible key names)
    [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP '(?:player_token|playerToken|auth_token|accessToken|Token|Authorization)"[^"]*"[[:space:]]*=[[:space:]]*"\K[^"]+' | head -1)
    [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP '"(?:player_token|playerToken|auth_token|accessToken)"[[:space:]]*:[[:space:]]*"\K[^"]+' | head -1)
    [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP '<string name="(?:player_token|playerToken|auth_token|accessToken)">\K[^<]+' | head -1)
    
    # Extract player ID
    [ -z "$PLAYER_ID" ] && PLAYER_ID=$(echo "$PREF_CONTENT" | grep -oP '(?:player_id|playerId|PlayerId)"[^"]*"[[:space:]]*=[[:space:]]*"\K[^"]+' | head -1)
    [ -z "$PLAYER_ID" ] && PLAYER_ID=$(echo "$PREF_CONTENT" | grep -oP '"(?:player_id|playerId|PlayerId)"[[:space:]]*:[[:space:]]*"\K[^"]+' | head -1)
    [ -z "$PLAYER_ID" ] && PLAYER_ID=$(echo "$PREF_CONTENT" | grep -oP '<string name="(?:player_id|playerId|PlayerId)">\K[^<]+' | head -1)
    
    # Extract player name
    [ -z "$PLAYER_NAME" ] && PLAYER_NAME=$(echo "$PREF_CONTENT" | grep -oP '(?:player_name|playerName)"[^"]*"[[:space:]]*=[[:space:]]*"\K[^"]+' | head -1)
    [ -z "$PLAYER_NAME" ] && PLAYER_NAME=$(echo "$PREF_CONTENT" | grep -oP '"(?:player_name|playerName)"[[:space:]]*:[[:space:]]*"\K[^"]+' | head -1)
    
    # Extract device ID
    [ -z "$DEVICE_ID_VAL" ] && DEVICE_ID_VAL=$(echo "$PREF_CONTENT" | grep -oP '(?:device_id|deviceId|DeviceId)"[^"]*"[[:space:]]*=[[:space:]]*"\K[^"]+' | head -1)
    [ -z "$DEVICE_ID_VAL" ] && DEVICE_ID_VAL=$(echo "$PREF_CONTENT" | grep -oP '"(?:device_id|deviceId|DeviceId)"[[:space:]]*:[[:space:]]*"\K[^"]+' | head -1)
done

echo -e "  ${GREEN}Saved${NC} $(ls "$PREFS_DIR/" 2>/dev/null | wc -l) pref files to shared_prefs/"

# ============================================================
# STEP 5: Search deeper for tokens in all pref files
# ============================================================
echo -e "\n${YELLOW}[5] Deep scanning prefs for tokens...${NC}"

# If we didn't find tokens with specific key names, search broadly
if [ -z "$PLAYER_TOKEN" ]; then
    echo -e "  ${CYAN}Searching for token-like strings...${NC}"
    
    # Search all pref files for anything that looks like a token
    for pref_file in "$PREFS_DIR"/*; do
        [ ! -f "$pref_file" ] && continue
        
        # Look for long alphanumeric strings (likely tokens)
        LONG_STRINGS=$(grep -oP '[a-zA-Z0-9_-]{30,}' "$pref_file" 2>/dev/null || true)
        if [ -n "$LONG_STRINGS" ]; then
            echo -e "  Found in $(basename "$pref_file"):"
            echo "$LONG_STRINGS" | head -5 | while read str; do
                [ -n "$str" ] && echo -e "    ${CYAN}$str${NC}"
            done
        fi
        
        # Look for JWT tokens
        JWT_TOKENS=$(grep -oP 'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+' "$pref_file" 2>/dev/null || true)
        if [ -n "$JWT_TOKENS" ]; then
            echo -e "  ${GREEN}JWT token found in $(basename "$pref_file")!${NC}"
            PLAYER_TOKEN=$(echo "$JWT_TOKENS" | head -1)
        fi
        
        # Look for GUID/UUID style tokens
        GUID_TOKENS=$(grep -oP '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' "$pref_file" 2>/dev/null || true)
        if [ -n "$GUID_TOKENS" ]; then
            echo -e "  GUIDs found in $(basename "$pref_file"):"
            echo "$GUID_TOKENS" | head -5 | while read g; do
                [ -n "$g" ] && echo -e "    $g"
            done
        fi
    done
fi

# ============================================================
# STEP 6: Dump raw content of important files
# ============================================================
echo -e "\n${YELLOW}[6] Dumping pref file contents...${NC}"

for pref_file in "$PREFS_DIR"/*; do
    [ ! -f "$pref_file" ] && continue
    PF_SIZE=$(wc -c < "$pref_file" 2>/dev/null || echo 0)
    if [ "$PF_SIZE" -gt 50 ]; then
        echo -e "\n  --- $(basename "$pref_file") (${PF_SIZE} bytes) ---"
        head -40 "$pref_file" 2>/dev/null | while read line; do
            echo -e "    $line"
        done
        TOTAL_LINES=$(wc -l < "$pref_file" 2>/dev/null || echo 0)
        if [ "$TOTAL_LINES" -gt 40 ]; then
            echo -e "    ... ($TOTAL_LINES total lines)"
        fi
    fi
done

# ============================================================
# STEP 7: Extract database files
# ============================================================
echo -e "\n${YELLOW}[7] Looking for databases...${NC}"

DB_FILES=$(run_adb "find $CODYCROSS_DATA -maxdepth 3 \( -name '*.db' -o -name '*.litedb' -o -name '*.sqlite' -o -name '*LiteDB*' -o -name '*database*' \) -type f 2>/dev/null" || true)
if [ -n "$DB_FILES" ]; then
    echo "$DB_FILES" | while read db_path; do
        [ -z "$db_path" ] && continue
        DB_NAME=$(basename "$db_path")
        run_adb "cat '$db_path'" > "$EXTRACT_DIR/$DB_NAME" 2>/dev/null || true
        if [ -s "$EXTRACT_DIR/$DB_NAME" ]; then
            echo -e "  ${GREEN}Saved${NC}: $DB_NAME ($(wc -c < "$EXTRACT_DIR/$DB_NAME") bytes)"
        fi
    done
else
    echo -e "  (no database files found)"
fi

# ============================================================
# STEP 8: Extract Unity Addressable bundles (.cody files)
# ============================================================
echo -e "\n${YELLOW}[8] Looking for Unity Addressable bundles...${NC}"

AA_CHECK=$(run_adb "ls $CODYCROSS_DATA/files/aa/ 2>/dev/null" | head -5 || true)
if [ -n "$AA_CHECK" ]; then
    echo -e "  ${GREEN}Found Unity Addressables!${NC}"
    
    # Get all bundle and cody files
    BUNDLE_FILES=$(run_adb "find $CODYCROSS_DATA/files/aa/ \( -name '*.bundle' -o -name '*.cody' \) -type f 2>/dev/null" || true)
    BUNDLE_COUNT=$(echo "$BUNDLE_FILES" | grep -c '.' || echo 0)
    echo -e "  Found $BUNDLE_COUNT bundle files"
    
    if [ "$BUNDLE_COUNT" -gt 0 ] && [ "$BUNDLE_COUNT" -lt 50 ]; then
        echo "$BUNDLE_FILES" | while read bp; do
            [ -z "$bp" ] && continue
            BN=$(basename "$bp")
            run_adb "cat '$bp'" > "$BUNDLE_DIR/$BN" 2>/dev/null || true
            echo -e "  ${GREEN}Saved${NC}: $BN"
        done
    elif [ "$BUNDLE_COUNT" -ge 50 ]; then
        echo -e "  ${YELLOW}Too many bundles ($BUNDLE_COUNT). Only listing first 20:${NC}"
        echo "$BUNDLE_FILES" | head -20 | while read bp; do
            [ -n "$bp" ] && echo -e "    $bp"
        done
        echo -e "  ${CYAN}Run manually to pull specific files if needed.${NC}"
    fi
    
    # Save catalog files
    run_adb "find $CODYCROSS_DATA/files/aa/ -name 'catalog*' -type f 2>/dev/null" | while read cp; do
        [ -z "$cp" ] && continue
        CN=$(basename "$cp")
        run_adb "cat '$cp'" > "$BUNDLE_DIR/$CN" 2>/dev/null || true
        echo -e "  ${GREEN}Saved${NC}: $CN (catalog)"
    done
else
    echo -e "  ${YELLOW}No addressables dir at $CODYCROSS_DATA/files/aa/${NC}"
    
    # Check other common locations
    for alt in "files/UnityData" "files/Unity" "files/Bundles" "databases" "cache"; do
        ALT_CHECK=$(run_adb "ls $CODYCROSS_DATA/$alt/ 2>/dev/null" | head -3 || true)
        if [ -n "$ALT_CHECK" ]; then
            echo -e "  Found: $CODYCROSS_DATA/$alt/"
            echo "$ALT_CHECK" | while read l; do [ -n "$l" ] && echo -e "    $l"; done
        fi
    done
fi

# Look for daily/password specific files
DAILY_FILES=$(run_adb "find $CODYCROSS_DATA -name '*daily*' -o -name '*password*' -o -name '*tc_daily*' 2>/dev/null" || true)
if [ -n "$DAILY_FILES" ]; then
    echo -e "\n  ${GREEN}Daily/Password files found:${NC}"
    echo "$DAILY_FILES" | while read df; do
        [ -n "$df" ] && echo -e "    $df"
    done
fi

# ============================================================
# STEP 9: Extract URLs/config from all extracted files
# ============================================================
echo -e "\n${YELLOW}[9] Scanning for API URLs in extracted data...${NC}"

for f in "$PREFS_DIR"/* "$EXTRACT_DIR"/*.json "$EXTRACT_DIR"/*.xml 2>/dev/null; do
    [ ! -f "$f" ] && continue
    URLS=$(grep -oP 'https?://[a-zA-Z0-9._/-]+' "$f" 2>/dev/null | sort -u || true)
    if [ -n "$URLS" ]; then
        echo -e "  URLs in $(basename "$f"):"
        echo "$URLS" | while read url; do
            [ -n "$url" ] && echo -e "    ${CYAN}$url${NC}"
        done
    fi
done

# ============================================================
# STEP 10: Save results
# ============================================================
echo -e "\n${YELLOW}[10] Saving results...${NC}"

TIMESTAMP=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')

cat > "$OUTPUT_FILE" << JSONEOF
{
    "extracted_at": "$TIMESTAMP",
    "player_token": "$PLAYER_TOKEN",
    "player_id": "$PLAYER_ID",
    "player_name": "$PLAYER_NAME",
    "device_id": "$DEVICE_ID_VAL",
    "app_version": "$CODYCROSS_VER",
    "package": "$CODYCROSS_PKG",
    "device_serial": "$DEVICE_ID",
    "files_extracted": {
        "shared_prefs": $(ls "$PREFS_DIR/" 2>/dev/null | wc -l),
        "bundles": $(ls "$BUNDLE_DIR/" 2>/dev/null | wc -l),
        "databases": $(find "$EXTRACT_DIR" -maxdepth 1 \( -name '*.db' -o -name '*.litedb' \) 2>/dev/null | wc -l)
    }
}
JSONEOF

echo -e "  ${GREEN}Saved${NC}: $OUTPUT_FILE"

# ============================================================
# FINAL SUMMARY
# ============================================================
echo -e "\n${GREEN}==========================================${NC}"
echo -e "${GREEN}  EXTRACTION COMPLETE!${NC}"
echo -e "${GREEN}==========================================${NC}"

echo -e "\n${BLUE}Results:${NC}"
echo -e "  Player Token: ${CYAN}${PLAYER_TOKEN:-NOT FOUND}${NC}"
echo -e "  Player ID:    ${CYAN}${PLAYER_ID:-NOT FOUND}${NC}"
echo -e "  Player Name:  ${CYAN}${PLAYER_NAME:-NOT FOUND}${NC}"
echo -e "  Device ID:    ${CYAN}${DEVICE_ID_VAL:-NOT FOUND}${NC}"

echo -e "\n${BLUE}Files saved:${NC}"
echo -e "  $EXTRACT_DIR/player_token.json"
echo -e "  $EXTRACT_DIR/shared_prefs/ ($(ls "$PREFS_DIR/" | wc -l) files)"
echo -e "  $EXTRACT_DIR/bundles/ ($(ls "$BUNDLE_DIR/" | wc -l) files)"

echo -e "\n${BLUE}Next step:${NC}"

if [ -n "$PLAYER_TOKEN" ]; then
    echo -e "  ${GREEN}Token found! Run:${NC}"
    echo -e "  ${CYAN}cd ~/codycross && python3 fetch_daily_api.py${NC}"
else
    echo -e "  ${YELLOW}No token auto-detected. Check the raw pref dumps above.${NC}"
    echo -e "  Look for long strings near 'token', 'auth', or 'key'."
    echo -e "  You can manually edit $OUTPUT_FILE to add your token."
    echo -e "  Then run: ${CYAN}python3 fetch_daily_api.py${NC}"
fi

echo ""
