#!/bin/bash
# ============================================================
# CodyCross AES Key Extraction - Local Emulator Helper
# ============================================================
# One-command script: boot emulator → install Frida → 
# install CodyCross → run hooks → extract AES key → save JSON
#
# Prerequisites:
#   - Android SDK with emulator
#   - Python 3 with pip
#   - ADB in PATH
#
# Usage:
#   chmod +x scripts/emulator-extract.sh
#   ./scripts/emulator-extract.sh
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  CodyCross AES Key Extraction Script${NC}"
echo -e "${BLUE}==========================================${NC}"

# ============================================================
# STEP 1: Check Prerequisites
# ============================================================

echo -e "\n${YELLOW}[1] Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] Python 3 not found${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python 3: $(python3 --version)"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}[!] pip3 not found${NC}"
    exit 1
fi

# Check ADB
if ! command -v adb &> /dev/null; then
    echo -e "${RED}[!] adb not found. Install Android SDK platform-tools.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} ADB: $(adb version | head -1)"

# Check emulator
if ! command -v emulator &> /dev/null; then
    echo -e "${RED}[!] emulator not found. Install Android SDK tools.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Emulator found"

# Install Frida
echo -e "\n${YELLOW}[2] Installing Frida tools...${NC}"
pip3 install frida-tools --quiet 2>/dev/null
FRIDA_VERSION=$(frida --version 2>/dev/null | head -1)
echo -e "  ${GREEN}✓${NC} Frida: $FRIDA_VERSION"

# ============================================================
# STEP 2: Setup Emulator
# ============================================================

echo -e "\n${YELLOW}[3] Setting up Android emulator...${NC}"

# Check for existing emulator
AVD_NAME=$(emulator -list-avds 2>/dev/null | head -1)
if [ -z "$AVD_NAME" ]; then
    echo "  No AVD found. Creating one with api 29 x86..."
    echo "no" | avdmanager create avd -n codycross_extract -k "system-images;android-29;default;x86" -d "pixel_6" --force 2>/dev/null || true
    AVD_NAME="codycross_extract"
fi
echo -e "  ${GREEN}✓${NC} Using AVD: $AVD_NAME"

# Kill existing emulator
adb kill-server 2>/dev/null || true
sleep 1

# Start emulator in background
echo -e "  Starting emulator..."
emulator -avd "$AVD_NAME" -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect &
EMULATOR_PID=$!

# Wait for boot
echo -e "  Waiting for device to boot..."
adb wait-for-device
BOOT_WAIT=0
while [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != "1" ]; do
    sleep 2
    BOOT_WAIT=$((BOOT_WAIT + 2))
    if [ $BOOT_WAIT -gt 120 ]; then
        echo -e "${RED}[!] Device failed to boot in 120s${NC}"
        kill $EMULATOR_PID 2>/dev/null || true
        exit 1
    fi
    echo -e "  Waiting... (${BOOT_WAIT}s)"
done
echo -e "  ${GREEN}✓${NC} Device booted"

# ============================================================
# STEP 3: Download and Install CodyCross APK
# ============================================================

echo -e "\n${YELLOW}[4] Installing CodyCross APK...${NC}"

APK_PATH=""
# Check if APK was already downloaded
for p in /tmp/CodyCross*.apk /tmp/codycross.apks ~/Downloads/CodyCross*.apk; do
    if [ -f "$p" ]; then
        APK_PATH="$p"
        break
    fi
done

if [ -z "$APK_PATH" ]; then
    echo -e "  Downloading CodyCross APK..."
    curl -L -o /tmp/codycross.apks \
        "https://static.apkcombo.com/apk/2/com.fanatee.cody/405.674140609cedc1410daf86fa84804edfbf1d4104.apks" 2>/dev/null || \
    curl -L -A "Mozilla/5.0" -o /tmp/codycross.apks \
        "https://d.apkpure.net/b/APK/com.fanatee.cody?version=latest" 2>/dev/null || \
    echo -e "${YELLOW}[!] Could not auto-download. Place APK at /tmp/codycross.apks${NC}"
    
    APK_PATH="/tmp/codycross.apks"
fi

if [ -f "$APK_PATH" ]; then
    echo -e "  Installing APK..."
    if [[ "$APK_PATH" == *.apks ]]; then
        # XAPK format - extract and install
        mkdir -p /tmp/codycross_xapk
        unzip -o "$APK_PATH" -d /tmp/codycross_xapk/ > /dev/null 2>&1
        for apk in /tmp/codycross_xapk/*.apk; do
            adb install -r -t "$apk" 2>/dev/null || true
        done
    else
        adb install -r "$APK_PATH" 2>/dev/null || true
    fi
    echo -e "  ${GREEN}✓${NC} APK installed"
else
    echo -e "${YELLOW}[!] No APK found. Please install CodyCross manually.${NC}"
fi

# ============================================================
# STEP 4: Install Frida Server
# ============================================================

echo -e "\n${YELLOW}[5] Setting up Frida server on device...${NC}"

# Download frida-server for the emulator architecture (x86)
ARCH=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
echo "  Device arch: $ARCH"

if [[ "$ARCH" == *x86* ]]; then
    FRIDA_ARCH="x86"
elif [[ "$ARCH" == *arm* ]]; then
    FRIDA_ARCH="arm64"
else
    FRIDA_ARCH="x86"
fi

FRIDA_SERVER_URL="https://github.com/frida/frida/releases/download/${FRIDA_VERSION}/frida-server-${FRIDA_VERSION}-android-${FRIDA_ARCH}.xz"
FRIDA_SERVER_PATH="/tmp/frida-server-${FRIDA_ARCH}"

if [ ! -f "$FRIDA_SERVER_PATH" ]; then
    echo "  Downloading frida-server for ${FRIDA_ARCH}..."
    curl -L -o "${FRIDA_SERVER_PATH}.xz" "$FRIDA_SERVER_URL" 2>/dev/null
    xz -d -f "${FRIDA_SERVER_PATH}.xz" 2>/dev/null || true
    chmod +x "$FRIDA_SERVER_PATH"
fi

if [ -f "$FRIDA_SERVER_PATH" ]; then
    adb push "$FRIDA_SERVER_PATH" /data/local/tmp/frida-server
    adb shell chmod 755 /data/local/tmp/frida-server
    echo -e "  ${GREEN}✓${NC} Frida server pushed"
    
    adb shell "/data/local/tmp/frida-server -D &"
    sleep 2
    echo -e "  ${GREEN}✓${NC} Frida server started"
    
    # Verify
    frida-ps -U 2>/dev/null | head -5
    echo -e "  ${GREEN}✓${NC} Frida connection verified"
else
    echo -e "${RED}[!] Failed to download frida-server${NC}"
    exit 1
fi

# ============================================================
# STEP 5: Run Frida Hooks
# ============================================================

echo -e "\n${YELLOW}[6] Running Frida hooks to extract AES key...${NC}"
echo -e "  ${BLUE}Launch CodyCross and open a puzzle to trigger decryption${NC}"
echo -e "  ${BLUE}The hooks will automatically capture the key${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRIDA_SCRIPT="${SCRIPT_DIR}/frida-extract.js"

if [ ! -f "$FRIDA_SCRIPT" ]; then
    echo -e "${RED}[!] Frida script not found: $FRIDA_SCRIPT${NC}"
    exit 1
fi

# Run Frida for up to 5 minutes
OUTPUT_FILE="/tmp/frida-extract-output-$(date +%Y%m%d_%H%M%S).log"
timeout 300 frida -U -f com.fanatee.cody -l "$FRIDA_SCRIPT" --no-pause 2>&1 | tee "$OUTPUT_FILE" || true

# Also try attaching to running process
timeout 60 frida -U -n "CodyCross" -l "$FRIDA_SCRIPT" 2>&1 | tee -a "$OUTPUT_FILE" || true

# ============================================================
# STEP 6: Process Results
# ============================================================

echo -e "\n${YELLOW}[7] Processing extraction results...${NC}"

# Extract keys from output
FOUND_KEY=""

# Try to find AES-256 key in output
AES_KEY=$(grep -oP 'AES-256 KEY CAPTURED.*?Key \(hex\): \K[a-f0-9]{64}' "$OUTPUT_FILE" 2>/dev/null | head -1)
if [ -n "$AES_KEY" ]; then
    FOUND_KEY="$AES_KEY"
fi

# Try other patterns
if [ -z "$FOUND_KEY" ]; then
    FOUND_KEY=$(grep -oP '"key_hex"\s*:\s*"[a-f0-9]{64}"' "$OUTPUT_FILE" 2>/dev/null | head -1 | grep -oP '[a-f0-9]{64}')
fi

if [ -z "$FOUND_KEY" ]; then
    FOUND_KEY=$(grep -oP 'Key \(hex\): \K[a-f0-9]{64}' "$OUTPUT_FILE" 2>/dev/null | head -1)
fi

if [ -z "$FOUND_KEY" ] && [ -f /tmp/frida-result.json ]; then
    FOUND_KEY=$(python3 -c "
import json
try:
    with open('/tmp/frida-result.json') as f:
        data = json.load(f)
    if isinstance(data, dict) and 'key_hex' in data:
        print(data['key_hex'])
    elif isinstance(data, dict) and 'keys' in data:
        for k in data['keys']:
            if k.get('length') == 32:
                print(k['hex'])
                break
except: pass
" 2>/dev/null)
fi

# ============================================================
# STEP 7: Save Results
# ============================================================

if [ -n "$FOUND_KEY" ]; then
    echo -e "\n${GREEN}==========================================${NC}"
    echo -e "${GREEN}  ✅ AES-256 KEY SUCCESSFULLY EXTRACTED!${NC}"
    echo -e "${GREEN}==========================================${NC}"
    echo -e "  Key: ${FOUND_KEY}"
    echo -e "${GREEN}==========================================${NC}"
    
    # Save to file
    RESULT_FILE="${SCRIPT_DIR}/../extracted-key.json"
    echo "{\"key_hex\": \"$FOUND_KEY\", \"key_length\": 32, \"algorithm\": \"AES-256-CBC\", \"extracted_at\": \"$(date -Iseconds)\", \"source\": \"frida_runtime_extraction\"}" > "$RESULT_FILE"
    echo -e "\n  Key saved to: $RESULT_FILE"
    
    # Print instructions
    echo -e "\n${BLUE}Next steps:${NC}"
    echo -e "  1. Add this key as a GitHub Secret:"
    echo -e "     Go to your repo → Settings → Secrets → Actions"
    echo -e "     Name: GAME_AES_KEY"
    echo -e "     Value: $FOUND_KEY"
    echo -e ""
    echo -e "  2. Or set it locally:"
    echo -e "     export GAME_AES_KEY=$FOUND_KEY"
    echo -e "     python3 fetcher/fetch_answers.py"
    echo -e ""
    echo -e "  3. The daily-extract workflow will use this key automatically"
else
    echo -e "\n${RED}==========================================${NC}"
    echo -e "${RED}  ❌ Key not found in this session${NC}"
    echo -e "${RED}==========================================${NC}"
    echo -e "\n${YELLOW}Tips:${NC}"
    echo -e "  - Make sure CodyCross is fully installed"
    echo -e "  - Open the app and navigate to a puzzle level"
    echo -e "  - The decryption only happens when a puzzle loads"
    echo -e "  - Check $OUTPUT_FILE for details"
    echo -e ""
    echo -e "  Alternatively, try static binary analysis:"
    echo -e "  - Use Il2CppDumper + Ghidra on libil2cpp.so"
    echo -e "  - Look for PuzzleCrypto class initialization"
fi

# Cleanup
echo -e "\n${YELLOW}[8] Cleaning up...${NC}"
kill $EMULATOR_PID 2>/dev/null || true
adb kill-server 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Done"

echo -e "\n${BLUE}Full output saved to: $OUTPUT_FILE${NC}"
