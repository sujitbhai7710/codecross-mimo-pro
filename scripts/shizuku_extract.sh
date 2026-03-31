#!/bin/bash
# ============================================================
# CodyCross Data Extractor - Shizuku (Non-Rooted Phone)
# ============================================================
# Works on NON-ROOTED phones using Shizuku + Wireless Debugging
# Extracts: Player Token, Player ID, App Config, .cody bundles
#
# PREREQUISITES (on your phone):
#   1. Shizuku app installed + started (using wireless debugging)
#   2. Termux installed
#   3. CodyCross game installed and opened at least once
#   4. Termux: pkg install termux-api
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

# Paths - everything goes into ~/codycross/
BASE_DIR="$HOME/codycross"
EXTRACT_DIR="$BASE_DIR/extracted"
BUNDLE_DIR="$EXTRACT_DIR/bundles"
PREFS_DIR="$EXTRACT_DIR/shared_prefs"
OUTPUT_FILE="$EXTRACT_DIR/player_token.json"

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
mkdir -p "$BASE_DIR"
mkdir -p "$EXTRACT_DIR"
mkdir -p "$BUNDLE_DIR"
mkdir -p "$PREFS_DIR"
echo -e "  ${GREEN}Done${NC}: $BASE_DIR/"

# ============================================================
# STEP 1: Check Shizuku is running
# ============================================================
echo -e "\n${YELLOW}[1] Checking Shizuku...${NC}"

# Check if Shizuku is running by trying to use it
# Shizuku provides ADB shell via: shizuku_shell or via ADB service
SHIZUKU_RUNNING=false

# Method 1: Check via termux-am (if termux-api installed)
if command -v shizuku &> /dev/null 2>&1; then
    echo -e "  ${GREEN}shizuku command found${NC}"
    SHIZUKU_RUNNING=true
fi

# Method 2: Check ADB over wireless (Shizuku starts ADB server on port)
# Shizuku typically listens on TCP:5555 or uses a Unix socket
if [ "$SHIZUKU_RUNNING" = false ]; then
    # Try connecting via Shizuku's ADB service
    # On newer Shizuku, it provides: shizuku_shell through its own service
    if command -v termux-am &> /dev/null 2>&1; then
        echo -e "  ${GREEN}termux-am found${NC}"
        SHIZUKU_RUNNING=true
    fi
fi

if [ "$SHIZUKU_RUNNING" = false ]; then
    echo -e "  ${YELLOW}Could not auto-detect Shizuku${NC}"
fi
echo -e "  ${GREEN}Proceeding...${NC}"

# ============================================================
# STEP 2: Try multiple Shizuku access methods
# ============================================================
echo -e "\n${YELLOW}[2] Connecting to Shizuku shell...${NC}"

# We'll try 3 methods to get ADB-level shell access
# Store the command that works
SHELL_CMD=""
METHOD_USED=""

# --- METHOD 1: Direct Shizuku shell via adb ---
# Shizuku acts as an ADB server. Connect to it.
echo -e "  ${CYAN}Trying Method 1: ADB connect via Shizuku...${NC}"

# First try to find Shizuku's port (commonly 5555 or random high port)
if command -v adb &> /dev/null 2>&1; then
    # Kill any existing ADB server
    adb kill-server 2>/dev/null || true
    sleep 1

    # Connect to localhost - Shizuku typically binds to 127.0.0.1:5555
    # when wireless debugging is enabled
    adb connect 127.0.0.1:5555 2>/dev/null && {
        echo -e "  ${GREEN}Connected via ADB localhost:5555${NC}"
        # Test if we can access app data
        TEST_ACCESS=$(adb -s 127.0.0.1:5555 shell "ls $CODYCROSS_DATA/shared_prefs/ 2>/dev/null" | head -3)
        if [ -n "$TEST_ACCESS" ]; then
            SHELL_CMD="adb -s 127.0.0.1:5555 shell"
            METHOD_USED="adb_localhost"
        fi
    } || echo -e "  ${YELLOW}ADB localhost:5555 failed${NC}"

    # Try port 62001 (another common Shizuku port)
    if [ -z "$SHELL_CMD" ]; then
        adb connect 127.0.0.1:62001 2>/dev/null && {
            TEST_ACCESS=$(adb -s 127.0.0.1:62001 shell "ls $CODYCROSS_DATA/shared_prefs/ 2>/dev/null" | head -3)
            if [ -n "$TEST_ACCESS" ]; then
                SHELL_CMD="adb -s 127.0.0.1:62001 shell"
                METHOD_USED="adb_62001"
            fi
        } || echo -e "  ${YELLOW}ADB localhost:62001 failed${NC}"
    fi
fi

# --- METHOD 2: Shizuku app direct shell ---
# Newer Shizuku (v13+) allows running shell commands directly
if [ -z "$SHELL_CMD" ]; then
    echo -e "  ${CYAN}Trying Method 2: Shizuku direct shell...${NC}"
    
    # Shizuku provides a shell via its app component
    # This uses am broadcast to send commands to Shizuku
    if command -v termux-am &> /dev/null 2>&1; then
        # Request Shizuku to run a shell command
        # The output comes back via broadcast result
        RESULT=$(termux-am broadcast \
            -n moe.shizuku.privileged.api/.intent.RequestCommandAction \
            --es command "ls $CODYCROSS_DATA/shared_prefs/" \
            --ei timeout 10 2>/dev/null | grep -o 'result=' | head -1 || true)
        
        if [ -n "$RESULT" ]; then
            echo -e "  ${GREEN}Shizuku broadcast method works${NC}"
            METHOD_USED="shizuku_broadcast"
            # We'll use a helper function for this
        fi
    fi
fi

# --- METHOD 3: Shizuku ISHELL (recommended method for Termux) ---
if [ -z "$SHELL_CMD" ]; then
    echo -e "  ${CYAN}Trying Method 3: Shizuku ISHELL / direct executable...${NC}"
    
    # Check if shizuku or shizuku_shell binary exists in PATH
    for cmd in shizuku shizuku_shell ishell; do
        if command -v "$cmd" &> /dev/null 2>&1; then
            SHELL_CMD="$cmd"
            METHOD_USED="$cmd"
            echo -e "  ${GREEN}Found: $cmd${NC}"
            break
        fi
    done
    
    # Also check common Termux install locations
    for path in /data/data/com.termux/files/usr/bin/shizuku /data/data/com.termux/files/usr/bin/shizuku_shell; do
        if [ -f "$path" ]; then
            SHELL_CMD="$path"
            METHOD_USED="termux_shizuku"
            echo -e "  ${GREEN}Found: $path${NC}"
            break
        fi
    done
fi

# --- METHOD 4: Shizuku via su -c (if Shizuku provides su) ---
if [ -z "$SHELL_CMD" ]; then
    echo -e "  ${CYAN}Trying Method 4: Shizuku su provider...${NC}"
    
    # Shizuku can act as a root provider for specific apps
    # Test if 'su -c' works through Shizuku
    SU_TEST=$(su -c "id" 2>/dev/null || true)
    if echo "$SU_TEST" | grep -q "uid=0"; then
        SHELL_CMD="su -c"
        METHOD_USED="shizuku_su"
        echo -e "  ${GREEN}Shizuku su access works!${NC}"
    fi
fi

if [ -z "$SHELL_CMD" ] && [ -z "$METHOD_USED" ]; then
    echo -e "\n${RED}==========================================${NC}"
    echo -e "${RED}  ERROR: Cannot connect to Shizuku!${NC}"
    echo -e "${RED}==========================================${NC}"
    echo -e ""
    echo -e "${YELLOW}Please follow these steps:${NC}"
    echo -e ""
    echo -e "  1. Open ${CYAN}Shizuku${NC} app on your phone"
    echo -e "  2. Tap ${CYAN}'Start via Wireless Debugging'${NC}"
    echo -e "  3. Go to phone Settings > Developer Options"
    echo -e "  4. Enable ${CYAN}'Wireless Debugging'${NC}"
    echo -e "  5. Tap ${CYAN}'Pair device with pairing code'${NC}"
    echo -e "     - Note the IP:PORT and code shown"
    echo -e "  6. Go back to Shizuku, it should auto-detect"
    echo -e "  7. Tap ${CYAN}'Start'${NC} in Shizuku"
    echo -e "  8. Shizuku notification should appear"
    echo -e "  9. Come back to Termux and run this script again"
    echo -e ""
    echo -e "${YELLOW}Alternative: Install ADB in Termux:${NC}"
    echo -e "  pkg install android-tools"
    echo -e "  Then pair + connect:"
    echo -e "  adb pair <IP>:<PAIRING_PORT>"
    echo -e "  adb connect <IP>:<PORT>"
    echo -e ""
    echo -e "${YELLOW}Or install Shizuku shell helper:${NC}"
    echo -e "  In Shizuku app > menu > 'Manage shell permission'"
    echo -e "  Grant to Termux"
    echo -e ""
    exit 1
fi

echo -e "  ${GREEN}Using method: $METHOD_USED${NC}"

# ============================================================
# Helper function to run shell commands via Shizuku
# ============================================================
run_shizuku() {
    local cmd="$1"
    local result=""
    
    case "$METHOD_USED" in
        adb_localhost|adb_62001)
            result=$($SHELL_CMD "$cmd" 2>/dev/null)
            ;;
        shizuku_broadcast)
            # Use Shizuku broadcast to execute command
            # Output is captured via content provider or file
            result=$(termux-am broadcast \
                -n moe.shizuku.privileged.api/.intent.RequestCommandAction \
                --es command "$cmd" \
                --ei timeout 15 2>/dev/null)
            # Parse result from broadcast extras
            result=$(echo "$result" | sed -n 's/.*result=\(.*\)/\1/p' | head -1)
            ;;
        shizuku|shizuku_shell|ishell|termux_shizuku)
            result=$($SHELL_CMD "$cmd" 2>/dev/null)
            ;;
        shizuku_su)
            result=$(su -c "$cmd" 2>/dev/null)
            ;;
        *)
            result=$(eval "$SHELL_CMD \"$cmd\"" 2>/dev/null)
            ;;
    esac
    
    # Clean up carriage returns from ADB output
    echo "$result" | tr -d '\r'
}

# ============================================================
# STEP 3: Verify CodyCross is installed
# ============================================================
echo -e "\n${YELLOW}[3] Checking CodyCross installation...${NC}"

CODYCROSS_CHECK=$(run_shizuku "pm list packages | grep $CODYCROSS_PKG" 2>/dev/null || true)
if [ -z "$CODYCROSS_CHECK" ]; then
    echo -e "  ${RED}CodyCross NOT found! Install it from Play Store first.${NC}"
    exit 1
fi

# Get version
CODYCROSS_VER=$(run_shizuku "dumpsys package $CODYCROSS_PKG | grep versionName" 2>/dev/null | head -1 | grep -oP 'versionName=\K[^\s]+' || echo "unknown")
echo -e "  ${GREEN}Found${NC}: $CODYCROSS_PKG (v$CODYCROSS_VER)"

# Verify we can access app data
DATA_CHECK=$(run_shizuku "ls $CODYCROSS_DATA/ 2>/dev/null" | head -5 || true)
if [ -z "$DATA_CHECK" ]; then
    echo -e "  ${RED}Cannot access app data directory!${NC}"
    echo -e "  ${YELLOW}Make sure Shizuku has proper permissions.${NC}"
    echo -e "  In Shizuku app: Menu > Manage app permissions > Grant file access${NC}"
    exit 1
fi
echo -e "  ${GREEN}App data accessible${NC}: $(echo "$DATA_CHECK" | head -3 | tr '\n' ' ')"

# ============================================================
# STEP 4: Extract SharedPreferences (Player Token + ID)
# ============================================================
echo -e "\n${YELLOW}[4] Extracting SharedPreferences...${NC}"

# List all shared_prefs files
PREFS_FILES=$(run_shizuku "ls $CODYCROSS_DATA/shared_prefs/" 2>/dev/null || true)
echo -e "  Found prefs files:"
echo "$PREFS_FILES" | while read line; do
    [ -n "$line" ] && echo -e "    $line"
done

# Extract key preference files
PLAYER_TOKEN=""
PLAYER_ID=""
PLAYER_NAME=""
DEVICE_ID=""

for pref_file in $PREFS_FILES; do
    PREF_CONTENT=$(run_shizuku "cat $CODYCROSS_DATA/shared_prefs/$pref_file" 2>/dev/null || true)
    if [ -n "$PREF_CONTENT" ]; then
        # Save raw pref file
        echo "$PREF_CONTENT" > "$PREFS_DIR/$pref_file"
        
        # Extract player token
        if [ -z "$PLAYER_TOKEN" ]; then
            PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP 'player_token"\s*=\s*"\K[^"]+' | head -1 || true)
            # Try other key names
            [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP '"playerToken"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP 'auth_token"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP '"accessToken"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$PLAYER_TOKEN" ] && PLAYER_TOKEN=$(echo "$PREF_CONTENT" | grep -oP 'Token"\s*=\s*"\K[^"]+' | head -1 || true)
        fi
        
        # Extract player ID
        if [ -z "$PLAYER_ID" ]; then
            PLAYER_ID=$(echo "$PREF_CONTENT" | grep -oP 'player_id"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$PLAYER_ID" ] && PLAYER_ID=$(echo "$PREF_CONTENT" | grep -oP '"playerId"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$PLAYER_ID" ] && PLAYER_ID=$(echo "$PREF_CONTENT" | grep -oP 'PlayerId"\s*=\s*"\K[^"]+' | head -1 || true)
        fi
        
        # Extract player name
        if [ -z "$PLAYER_NAME" ]; then
            PLAYER_NAME=$(echo "$PREF_CONTENT" | grep -oP 'player_name"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$PLAYER_NAME" ] && PLAYER_NAME=$(echo "$PREF_CONTENT" | grep -oP '"playerName"\s*=\s*"\K[^"]+' | head -1 || true)
        fi
        
        # Extract device ID
        if [ -z "$DEVICE_ID" ]; then
            DEVICE_ID=$(echo "$PREF_CONTENT" | grep -oP 'device_id"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$DEVICE_ID" ] && DEVICE_ID=$(echo "$PREF_CONTENT" | grep -oP '"deviceId"\s*=\s*"\K[^"]+' | head -1 || true)
            [ -z "$DEVICE_ID" ] && DEVICE_ID=$(echo "$PREF_CONTENT" | grep -oP 'DeviceId"\s*=\s*"\K[^"]+' | head -1 || true)
        fi
    fi
done

echo -e "  ${GREEN}Saved${NC} $(ls "$PREFS_DIR/" | wc -l) pref files to $PREFS_DIR/"

# ============================================================
# STEP 5: Check LiteDB / Database files
# ============================================================
echo -e "\n${YELLOW}[5] Checking database files...${NC}"

# CodyCross uses LiteDB (local database) stored in app data
DB_CHECK=$(run_shizuku "find $CODYCROSS_DATA -name '*.db' -o -name '*.litedb' -o -name '*.sqlite' -o -name 'LiteDB*' 2>/dev/null" || true)
echo -e "  Database files found:"
if [ -n "$DB_CHECK" ]; then
    echo "$DB_CHECK" | while read line; do
        [ -n "$line" ] && echo -e "    $line"
    done
    
    # Pull database files
    echo "$DB_CHECK" | while read db_path; do
        [ -z "$db_path" ] && continue
        DB_NAME=$(basename "$db_path")
        run_shizuku "cat '$db_path'" > "$EXTRACT_DIR/$DB_NAME" 2>/dev/null || true
        if [ -s "$EXTRACT_DIR/$DB_NAME" ]; then
            echo -e "  ${GREEN}Saved${NC}: $DB_NAME ($(wc -c < "$EXTRACT_DIR/$DB_NAME") bytes)"
        fi
    done
else
    echo -e "    (none found - data may be in files or memory)"
fi

# Also check for any JSON/XML data files in app dir
DATA_FILES=$(run_shizuku "find $CODYCROSS_DATA/files -type f \( -name '*.json' -o -name '*.xml' -o -name '*.cfg' -o -name '*.dat' \) 2>/dev/null" || true)
if [ -n "$DATA_FILES" ]; then
    echo -e "  Data files found:"
    echo "$DATA_FILES" | while read line; do
        [ -n "$line" ] && echo -e "    $line"
    done
    
    echo "$DATA_FILES" | while read df_path; do
        [ -z "$df_path" ] && continue
        DF_NAME=$(basename "$df_path")
        run_shizuku "cat '$df_path'" > "$EXTRACT_DIR/$DF_NAME" 2>/dev/null || true
        if [ -s "$EXTRACT_DIR/$DF_NAME" ]; then
            echo -e "  ${GREEN}Saved${NC}: $DF_NAME ($(wc -c < "$EXTRACT_DIR/$DF_NAME") bytes)"
        fi
    done
fi

# ============================================================
# STEP 6: Extract .cody asset bundles (Daily Crossword data)
# ============================================================
echo -e "\n${YELLOW}[6] Looking for .cody asset bundles...${NC}"

# Unity Addressable assets are stored in:
# /data/data/com.fanatee.cody/files/aa/
# /data/data/com.fanatee.cody/files/aa/<hash>/
# Or in the Unity StreamingAssets path

AA_DIR=$(run_shizuku "ls $CODYCROSS_DATA/files/aa/ 2>/dev/null" | head -10 || true)
if [ -n "$AA_DIR" ]; then
    echo -e "  ${GREEN}Found Unity Addressables directory!${NC}"
    echo "$AA_DIR" | head -10
    
    # List bundle files
    BUNDLE_LIST=$(run_shizuku "find $CODYCROSS_DATA/files/aa/ -name '*.bundle' -o -name '*.cody' 2>/dev/null" || true)
    BUNDLE_COUNT=$(echo "$BUNDLE_LIST" | grep -c '.' || echo 0)
    echo -e "  Found $BUNDLE_COUNT bundle files"
    
    if [ "$BUNDLE_COUNT" -gt 0 ]; then
        echo "$BUNDLE_LIST" | while read bundle_path; do
            [ -z "$bundle_path" ] && continue
            BUNDLE_NAME=$(basename "$bundle_path")
            run_shizuku "cat '$bundle_path'" > "$BUNDLE_DIR/$BUNDLE_NAME" 2>/dev/null || true
            echo -e "  ${GREEN}Saved${NC}: $BUNDLE_NAME"
        done
    fi
    
    # Also list the catalog.json/hash files for reference
    run_shizuku "find $CODYCROSS_DATA/files/aa/ -name 'catalog*' -o -name '*.hash' 2>/dev/null" | while read cat_path; do
        [ -z "$cat_path" ] && continue
        CAT_NAME=$(basename "$cat_path")
        run_shizuku "cat '$cat_path'" > "$BUNDLE_DIR/$CAT_NAME" 2>/dev/null || true
        echo -e "  ${GREEN}Saved${NC}: $CAT_NAME (catalog)"
    done
else
    echo -e "  ${YELLOW}Addressables dir not found at expected path${NC}"
    
    # Try alternate paths
    for alt_path in \
        "$CODYCROSS_DATA/files/UnityData" \
        "$CODYCROSS_DATA/files/Unity" \
        "$CODYCROSS_DATA/files/Bundles" \
        "$CODYCROSS_DATA/databases" \
        "$CODYCROSS_DATA/cache"; do
        ALT_CHECK=$(run_shizuku "ls '$alt_path/' 2>/dev/null" | head -5 || true)
        if [ -n "$ALT_CHECK" ]; then
            echo -e "  Found data at: $alt_path"
            echo "$ALT_CHECK" | head -5
        fi
    done
fi

# Also try to get the Unity cache (downloaded bundles)
UNITY_CACHE=$(run_shizuku "find $CODYCROSS_DATA -name '*daily*' -o -name '*password*' -o -name '*tc_daily*' 2>/dev/null" || true)
if [ -n "$UNITY_CACHE" ]; then
    echo -e "\n  ${GREEN}Found daily/password related files:${NC}"
    echo "$UNITY_CACHE" | while read line; do
        [ -n "$line" ] && echo -e "    $line"
    done
fi

# ============================================================
# STEP 7: Extract full SharedPreferences for token parsing
# ============================================================
echo -e "\n${YELLOW}[7] Deep scanning all prefs for tokens...${NC}"

# Scan ALL saved pref files for any token-like values
ALL_TOKENS=""
for pref_file in "$PREFS_DIR"/*; do
    [ ! -f "$pref_file" ] && continue
    # Find all values that look like tokens (long hex strings, JWTs, GUIDs)
    TOKEN_MATCHES=$(grep -oP '(?:token|Token|TOKEN|auth|Auth|key|Key)[^<="\s]*[=:]\s*["\x27]?([a-f0-9]{16,}|[A-Za-z0-9._-]{20,})' "$pref_file" 2>/dev/null || true)
    if [ -n "$TOKEN_MATCHES" ]; then
        ALL_TOKENS="$ALL_TOKENS\n$(basename "$pref_file"): $TOKEN_MATCHES"
    fi
done

if [ -n "$ALL_TOKENS" ]; then
    echo -e "  ${GREEN}Token-like values found:${NC}"
    echo -e "$ALL_TOKENS" | head -20
fi

# Also dump the raw content of the most likely pref file
echo -e "\n  ${CYAN}Raw SharedPreferences content (key files):${NC}"
for pref_file in "$PREFS_DIR"/*; do
    [ ! -f "$pref_file" ] && continue
    PF_SIZE=$(wc -c < "$pref_file")
    if [ "$PF_SIZE" -gt 100 ]; then  # Only show substantial files
        echo -e "\n  --- $(basename "$pref_file") (${PF_SIZE} bytes) ---"
        head -30 "$pref_file" 2>/dev/null | while read line; do
            echo -e "    $line"
        done
        echo -e "    ..."
    fi
done

# ============================================================
# STEP 8: Try to get the actual network requests / URLs
# ============================================================
echo -e "\n${YELLOW}[8] Extracting network config...${NC}"

# Check for OkHttp cache, Retrofit config, etc.
NET_CACHE=$(run_shizuku "find $CODYCROSS_DATA/cache -name '*' -type f 2>/dev/null" | head -20 || true)
if [ -n "$NET_CACHE" ]; then
    echo -e "  Cache files:"
    echo "$NET_CACHE" | while read line; do
        [ -n "$line" ] && echo -e "    $line"
    done
fi

# Get the app's base URL from config
echo -e "  ${CYAN}Checking for API URL in config files...${NC}"
for f in "$PREFS_DIR"/* "$EXTRACT_DIR"/*.json "$EXTRACT_DIR"/*.xml 2>/dev/null; do
    [ ! -f "$f" ] && continue
    URLS=$(grep -oP 'https?://[a-zA-Z0-9._/-]+' "$f" 2>/dev/null | sort -u || true)
    if [ -n "$URLS" ]; then
        echo -e "  URLs in $(basename "$f"):"
        echo "$URLS" | while read url; do
            [ -n "$url" ] && echo -e "    $url"
        done
    fi
done

# ============================================================
# STEP 9: Save results to JSON
# ============================================================
echo -e "\n${YELLOW}[9] Saving results...${NC}"

TIMESTAMP=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')

# Build JSON output
cat > "$OUTPUT_FILE" << JSONEOF
{
    "extracted_at": "$TIMESTAMP",
    "method": "$METHOD_USED",
    "player_token": "$PLAYER_TOKEN",
    "player_id": "$PLAYER_ID",
    "player_name": "$PLAYER_NAME",
    "device_id": "$DEVICE_ID",
    "app_version": "$CODYCROSS_VER",
    "package": "$CODYCROSS_PKG",
    "files_extracted": {
        "shared_prefs": $(ls "$PREFS_DIR/" 2>/dev/null | wc -l),
        "bundles": $(ls "$BUNDLE_DIR/" 2>/dev/null | wc -l),
        "databases": $(ls "$EXTRACT_DIR/"*.db "$EXTRACT_DIR/"*.litedb 2>/dev/null | wc -l)
    }
}
JSONEOF

echo -e "  ${GREEN}Saved${NC}: player_token.json"

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
echo -e "  Device ID:    ${CYAN}${DEVICE_ID:-NOT FOUND}${NC}"

echo -e "\n${BLUE}Files saved to:${NC}"
echo -e "  $EXTRACT_DIR/"
echo -e "    player_token.json   - Your credentials"
echo -e "    shared_prefs/       - App preferences (raw)"
echo -e "    bundles/            - Asset bundles (.cody files)"

echo -e "\n${BLUE}Next steps:${NC}"

if [ -n "$PLAYER_TOKEN" ]; then
    echo -e "  ${GREEN}Token found! Run the Python script:${NC}"
    echo -e "  cd ~/codycross"
    echo -e "  python3 fetch_daily_api.py"
    echo -e ""
    echo -e "  This will fetch daily crossword + password answers"
    echo -e "  from the CodyCross API using your player token."
else
    echo -e "  ${YELLOW}No player token found automatically.${NC}"
    echo -e ""
    echo -e "  ${CYAN}Manual steps to get the token:${NC}"
    echo -e "  1. Open CodyCross on your phone"
    echo -e "  2. Make sure you're logged in (Google/Facebook)"
    echo -e "  3. Run this script again after playing a level"
    echo -e "  4. Or check $PREFS_DIR/ files manually"
    echo -e "  5. Look for long strings after 'token' or 'auth'"
    echo -e ""
    echo -e "  ${CYAN}Alternative: Use mitmproxy${NC}"
    echo -e "  1. Set up mitmproxy on computer"
    echo -e "  2. Configure phone proxy"
    echo -e "  3. Open CodyCross - capture the API requests"
    echo -e "  4. Find the Authorization header in requests"
fi

echo -e "\n${BLUE}To set token manually:${NC}"
echo -e "  Edit: $OUTPUT_FILE"
echo -e "  Set: \"player_token\": \"YOUR_TOKEN_HERE\""
echo -e "  Then run: python3 fetch_daily_api.py"

echo ""
