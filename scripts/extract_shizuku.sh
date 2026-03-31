#!/bin/bash
# ============================================================
# CodyCross Data Extractor for Non-Rooted Android
# Works with Shizuku + Wireless Debugging + Termux
# ============================================================
#
# WHAT THIS DOES:
#   1. Connects to Shizuku (ADB-level access without root)
#   2. Extracts player token/session from game data
#   3. Finds and copies the addressable catalog from installed APK
#   4. Looks for cached daily crossword/password bundles
#   5. Copies everything to /sdcard/Download/codycross_extracted/
#
# SETUP (one-time):
#   1. Install Shizuku from GitHub or Play Store
#   2. Enable Developer Options on phone
#   3. Enable Wireless Debugging in Developer Options
#   4. Open Shizuku, tap "Start" (choose Wireless Debugging option)
#   5. In Termux: pkg install termux-api
#   6. Pair with: shizuku or via wireless debugging pairing
#
# USAGE:
#   bash extract_shizuku.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PKG="com.fanatee.cody"
OUT="/sdcard/Download/codycross_extracted"
LOG="$OUT/extract_log.txt"

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  CodyCross Data Extractor (Shizuku + Wireless Debug)${NC}"
echo -e "${CYAN}============================================================${NC}"

mkdir -p "$OUT"

log() {
    echo -e "$1" | tee -a "$LOG"
}

log "${GREEN}[INFO]${NC} Starting extraction at $(date)"

# ============================================================
# STEP 1: Connect to Shizuku
# ============================================================
log "\n${YELLOW}[STEP 1]${NC} Connecting to Shizuku..."

# Check if shizuku command is available
if command -v shizuku &>/dev/null; then
    log "${GREEN}[OK]${NC} Shizuku command found"
    
    # Try to get a shell via shizuku
    log "${GREEN}[INFO]${NC} Testing Shizuku access..."
    if shizuku -c "echo test" &>/dev/null; then
        log "${GREEN}[OK]${NC} Shizuku shell works!"
        SHIZUKU_CMD="shizuku -c"
    else
        log "${YELLOW}[WARN]${NC} Shizuku -c doesn't work, trying alternative..."
        SHIZUKU_CMD=""
    fi
else
    log "${YELLOW}[WARN]${NC} Shizuku command not found in PATH"
    log "${GREEN}[INFO]${NC} Trying direct ADB commands..."
    SHIZUKU_CMD=""
fi

# Try to use adb via Shizuku's wireless debugging
if [ -z "$SHIZUKU_CMD" ]; then
    # Check for adb
    if command -v adb &>/dev/null; then
        ADB_CMD="adb"
    elif [ -f "/system/bin/adb" ]; then
        ADB_CMD="/system/bin/adb"
    else
        ADB_CMD=""
    fi
    
    if [ -n "$ADB_CMD" ]; then
        # Try to connect to Shizuku's wireless debugging port
        # Shizuku typically uses port 5555 or a random port
        log "${GREEN}[INFO]${NC} Trying to connect to Shizuku via ADB..."
        
        # Try common ports
        for port in 5555 37189 37223 37893; do
            if $ADB_CMD connect 127.0.0.1:$port &>/dev/null; then
                log "${GREEN}[OK]${NC} Connected on port $port"
                SHIZUKU_CMD="$ADB_CMD shell"
                break
            fi
        done
        
        if [ -z "$SHIZUKU_CMD" ]; then
            # Maybe we need to pair first
            log "${YELLOW}[INFO]${NC} Couldn't auto-connect. Checking active connections..."
            $ADB_CMD devices 2>/dev/null | tee -a "$LOG" || true
        fi
    fi
fi

# Final fallback - try run-as (works with ADB without root for debuggable apps)
if [ -z "$SHIZUKU_CMD" ]; then
    log "${YELLOW}[WARN]${NC} No Shizuku/ADB connection found"
    log "${GREEN}[INFO]${NC} Trying run-as (limited access)..."
    
    # Check if app is debuggable
    if run-as $PKG echo test &>/dev/null; then
        log "${GREEN}[OK]${NC} App is debuggable! Using run-as"
        SHIZUKU_CMD="run-as $PKG"
    else
        log "${RED}[ERROR]${NC} Cannot access app data!"
        log "${YELLOW}[HELP]${NC} Make sure Shizuku is running:"
        log "  1. Open Shizuku app"
        log "  2. Tap 'Start'"
        log "  3. Select 'Wireless debugging'"
        log "  4. Or in Developer Options -> Wireless Debugging, tap 'Pair device'"
        log "  5. Then re-run this script"
        
        # Try to at least get what we can from /sdcard
        extract_from_sdcard
        exit 1
    fi
fi

# ============================================================
# STEP 2: Find and access game data
# ============================================================
log "\n${YELLOW}[STEP 2]${NC} Accessing game data..."

GAME_DIR="/data/data/$PKG"
FILES_DIR="$GAME_DIR/files"
CACHE_DIR="$GAME_DIR/cache"
SHARED_DIR="$GAME_DIR/shared_prefs"
DB_DIR="$GAME_DIR/databases"

# List game directory structure
log "${GREEN}[INFO]${NC} Scanning game directories..."
$SHIZUKU_CMD "ls -la $GAME_DIR/" 2>&1 | tee -a "$LOG" || true
log ""
$SHIZUKU_CMD "ls -la $FILES_DIR/" 2>&1 | tee -a "$LOG" || true
log ""
$SHIZUKU_CMD "ls -la $SHARED_DIR/" 2>&1 | tee -a "$LOG" || true
log ""
$SHIZUKU_CMD "ls -la $DB_DIR/" 2>&1 | tee -a "$LOG" || true
log ""
$SHIZUKU_CMD "ls -la $GAME_DIR/code_cache/" 2>&1 | tee -a "$LOG" || true

# ============================================================
# STEP 3: Extract Player Token / Session
# ============================================================
log "\n${YELLOW}[STEP 3]${NC} Extracting player data..."

# Method A: SharedPreferences
log "${GREEN}[INFO]${NC} Checking SharedPreferences..."
for pref in $SHARED_DIR/*.xml; do
    $SHIZUKU_CMD "cat $pref" 2>/dev/null | tee -a "$LOG" | grep -iE "player|token|session|userid|google|facebook|uuid|id_" | head -30 || true
done

# Method B: LiteDB or SQLite database
log "\n${GREEN}[INFO]${NC} Checking databases..."
$SHIZUKU_CMD "find $FILES_DIR $DB_DIR -name '*.db' -o -name '*.sqlite' -o -name '*lite*' -o -name '*player*' -o -name '*session*' -o -name '*token*' 2>/dev/null" | tee -a "$LOG" || true

# Method C: Look for JSON config files
log "\n${GREEN}[INFO]${NC} Checking config/JSON files..."
$SHIZUKU_CMD "find $FILES_DIR -name '*.json' -o -name '*.cfg' -o -name '*.conf' 2>/dev/null" | tee -a "$LOG" || true

# Copy LiteDB if found
LITEDB=$( $SHIZUKU_CMD "find $FILES_DIR $DB_DIR -name 'LiteDB*' 2>/dev/null" | head -1 )
if [ -n "$LITEDB" ] && [ -f "$LITEDB" ]; then
    log "${GREEN}[OK]${NC} Found LiteDB: $LITEDB"
    $SHIZUKU_CMD "cat $LITEDB" > "$OUT/litedb_dump.bin" 2>/dev/null || \
    $SHIZUKU_CMD "cp $LITEDB $OUT/litedb.db" 2>/dev/null || true
    log "${GREEN}[INFO]${NC} Extracted strings from LiteDB:"
    strings "$OUT/litedb_dump.bin" 2>/dev/null | grep -iE "player|token|session|userid|google|uuid" | head -30 | tee -a "$LOG" || true
fi

# ============================================================
# STEP 4: Extract Addressable Catalog
# ============================================================
log "\n${YELLOW}[STEP 4]${NC} Looking for addressable catalogs..."

# The Unity Addressable system stores a local catalog
CATALOG_PATTERNS=(
    "$FILES_DIR/catalog*"
    "$FILES_DIR/*catalog*"
    "$FILES_DIR/*addressable*"
    "$CACHE_DIR/catalog*"
    "$CACHE_DIR/*catalog*"
    "$GAME_DIR/catalog*"
    "$FILES_DIR/aa/*catalog*"
    "$CACHE_DIR/aa/*catalog*"
)

for pattern in "${CATALOG_PATTERNS[@]}"; do
    FOUND=$( $SHIZUKU_CMD "find $pattern -type f 2>/dev/null" | head -5 )
    if [ -n "$FOUND" ]; then
        log "${GREEN}[OK]${NC} Found catalog files:"
        echo "$FOUND" | tee -a "$LOG"
        for f in $FOUND; do
            fname=$(basename "$f")
            log "  Copying: $f -> $OUT/$fname"
            $SHIZUKU_CMD "cat $f" > "$OUT/$fname" 2>/dev/null || \
            $SHIZUKU_CMD "cp $f $OUT/" 2>/dev/null || true
        done
    fi
done

# Also check the Unity StreamingAssets for bundled catalog
$SHIZUKU_CMD "find $GAME_DIR -name 'catalog_content*' -o -name 'catalog.json' -o -name 'addressables*catalog*' 2>/dev/null" | tee -a "$LOG" || true

# ============================================================
# STEP 5: Find Crossword/Password Bundle Files
# ============================================================
log "\n${YELLOW}[STEP 5]${NC} Searching for crossword/password bundles..."

# Search in all game directories for crossword/password content
$SHIZUKU_CMD "find $FILES_DIR $CACHE_DIR $GAME_DIR -type f \( -name '*crossword*' -o -name '*password*' -o -name '*daily*' -o -name '*tc_*' -o -name '*cruzadinha*' -o -name '*senha*' \) 2>/dev/null" | tee -a "$LOG" || true

# Search for .cody files (encrypted puzzle data)
log "\n${GREEN}[INFO]${NC} Searching for .cody puzzle files..."
CODY_FILES=$( $SHIZUKU_CMD "find $FILES_DIR -name '*.cody' 2>/dev/null" | head -20 )
if [ -n "$CODY_FILES" ]; then
    log "${GREEN}[OK]${NC} Found .cody files:"
    echo "$CODY_FILES" | tee -a "$LOG"
    
    mkdir -p "$OUT/cody_files"
    for f in $CODY_FILES; do
        fname=$(basename "$f")
        log "  Copying: $fname"
        $SHIZUKU_CMD "cat $f" > "$OUT/cody_files/$fname" 2>/dev/null || \
        $SHIZUKU_CMD "cp $f $OUT/cody_files/" 2>/dev/null || true
    done
else
    log "${YELLOW}[INFO]${NC} No .cody files found in app data"
    log "${GREEN}[INFO]${NC} .cody files might be in the APK itself (not extracted at install)"
fi

# Search for Unity AssetBundle files
log "\n${GREEN}[INFO]${NC} Searching for Unity bundle files in cache..."
BUNDLE_FILES=$( $SHIZUKU_CMD "find $CACHE_DIR $FILES_DIR -name '*.bundle' -o -name '*bundle*' 2>/dev/null" | grep -iE 'crossword|password|daily|tc_|content' | head -20 )
if [ -n "$BUNDLE_FILES" ]; then
    log "${GREEN}[OK]${NC} Found matching bundles:"
    echo "$BUNDLE_FILES" | tee -a "$LOG"
else
    # List all bundles for analysis
    ALL_BUNDLES=$( $SHIZUKU_CMD "find $CACHE_DIR $FILES_DIR -name '*.bundle' 2>/dev/null" | head -20 )
    if [ -n "$ALL_BUNDLES" ]; then
        log "${YELLOW}[INFO]${NC} Found ${#ALL_BUNDLES} bundle files (checking for daily content)..."
        echo "$ALL_BUNDLES" | tee -a "$LOG"
    else
        log "${YELLOW}[INFO]${NC} No cached bundles found"
        log "${GREEN}[INFO]${NC} Bundles may download when you open the crossword event"
    fi
fi

# ============================================================
# STEP 6: Extract from APK directly
# ============================================================
log "\n${YELLOW}[STEP 6]${NC} Extracting from installed APK..."

# Find the APK path
APK_PATH=$( $SHIZUKU_CMD "pm path $PKG 2>/dev/null" | head -1 | sed 's/package://' )
if [ -n "$APK_PATH" ]; then
    log "${GREEN}[OK]${NC} Found APK: $APK_PATH"
    
    # Copy APK for analysis
    APK_SIZE=$( $SHIZUKU_CMD "ls -la $APK_PATH 2>/dev/null" | awk '{print $5}' )
    log "${GREEN}[INFO]${NC} APK size: ${APK_SIZE} bytes"
    
    if [ "$APK_SIZE" -lt 100000000 ] 2>/dev/null; then
        # Small enough to copy (< 100MB)
        log "${GREEN}[INFO]${NC} Copying APK to $OUT/..."
        $SHIZUKU_CMD "cat $APK_PATH" > "$OUT/base.apk" 2>/dev/null || \
        $SHIZUKU_CMD "cp $APK_PATH $OUT/base.apk" 2>/dev/null || true
        
        # Extract catalog and metadata from APK
        log "${GREEN}[INFO]${NC} Searching APK for catalogs and metadata..."
        cd "$OUT"
        unzip -l base.apk 2>/dev/null | grep -iE "catalog|addressable|metadata|crossword|password|\.cody|\.json" | head -30 | tee -a "$LOG" || true
        
        # Extract the catalog
        unzip -o base.apk "assets/bin/Data/Managed/Metadata/global-metadata.dat" 2>/dev/null && \
            log "${GREEN}[OK]${NC} Extracted global-metadata.dat" || true
        
        unzip -o base.apk "*catalog*" 2>/dev/null && \
            log "${GREEN}[OK]${NC} Extracted catalog files" || true
        
        # Search for .cody files in APK
        CODY_COUNT=$( unzip -l base.apk 2>/dev/null | grep -c '\.cody' || echo 0 )
        if [ "$CODY_COUNT" -gt 0 ]; then
            log "${GREEN}[OK]${NC} Found $CODY_COUNT .cody files in APK!"
            unzip -l base.apk 2>/dev/null | grep '\.cody' | tee -a "$LOG"
            
            mkdir -p "$OUT/apk_cody_files"
            cd "$OUT/apk_cody_files"
            unzip -o ../base.apk "*.cody" 2>/dev/null || true
        fi
        
        # Search for crossword-related JSON
        CW_COUNT=$( unzip -l base.apk 2>/dev/null | grep -ci 'crossword\|password\|daily' || echo 0 )
        if [ "$CW_COUNT" -gt 0 ]; then
            log "${GREEN}[OK]${NC} Found $CW_COUNT crossword/password files in APK!"
            unzip -l base.apk 2>/dev/null | grep -i 'crossword\|password\|daily' | tee -a "$LOG"
            
            mkdir -p "$OUT/apk_crossword"
            cd "$OUT/apk_crossword"
            unzip -o ../base.apk "*crossword*" "*password*" "*daily*" 2>/dev/null || true
        fi
    else
        log "${YELLOW}[WARN]${NC} APK too large to copy (${APK_SIZE} bytes)"
        log "${GREEN}[INFO]${NC} Listing APK contents instead..."
        $SHIZUKU_CMD "ls -la $APK_PATH" 2>/dev/null | tee -a "$LOG"
    fi
else
    log "${YELLOW}[WARN]${NC} APK not found"
fi

# ============================================================
# STEP 7: Try to get player token via content provider
# ============================================================
log "\n${YELLOW}[STEP 7]${NC} Trying content provider access..."

# Some Unity games expose data via content providers
CONTENT_URI="content://$PKG.provider"
$SHIZUKU_CMD "content query --uri $CONTENT_URI 2>/dev/null" | tee -a "$LOG" || true

# ============================================================
# DONE
# ============================================================
log "\n${CYAN}============================================================${NC}"
log "${CYAN}  EXTRACTION COMPLETE${NC}"
log "${CYAN}============================================================${NC}"
log ""
log "All files saved to: $OUT"
log ""
log "NEXT STEPS:"
log "1. Check $OUT/litedb_dump.bin for player tokens"
log "2. Check $OUT/*.catalog* for addressable bundle keys"
log "3. Check $OUT/apk_crossword/ for bundled crossword data"
log "4. Upload files to https://z.ai chat for analysis"
log ""
log "To trigger crossword bundle download:"
log "  - Open CodyCross on your phone"
log "  - Go to Events -> Today's Crossword"  
log "  - Play the puzzle (this downloads the bundle)"
log "  - Re-run this script to capture the downloaded bundle"

echo ""
echo -e "${GREEN}Done! Check $OUT/ for extracted files${NC}"
