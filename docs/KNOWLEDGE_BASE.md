# CodyCross Daily Data Extraction - Complete Knowledge Base
# ============================================================
# This file contains EVERYTHING we've tried, found, and learned.
# DO NOT repeat any of these approaches. They have all been tested.
# Last updated: 2026-04-01
# ============================================================

## APP INFO
- Package: com.fanatee.cody
- Version: 2.8.1 (versionCode 405)
- API Level 24-35, targetSdk 35
- Engine: Unity 2021.3.20f1 (IL2CPP, arm64-v8a)
- Addressable asset packs: AddressablesAssetPack, UnityDataAssetPack, config.arm64_v8a
- flags: ALLOW_BACKUP (but backup blocked on Android 12+)
- NOT debuggable (run-as fails)
- Certificate pinning: YES (HTTP Toolkit HTTPS interception fails)

## API ENDPOINTS TESTED (game.codycross-game.com)
### WORKING (no auth needed):
- GET /Config/Get?appVersion=1.0.0 → Returns game config
- GET /Puzzle/GetMundo?mundo=N&country=US&appVersion=1.0.0 → Returns world data (UNENCRYPTED with appVersion=1.0.0)

### EXIST but NEED AUTH (return Ok:false, Status:1 without token):
- GET /TodaysPassword/Get → Daily password puzzle
- GET /Player/Login → Player login
- GET /Player/GetPuzzleSettings
- GET /Player/GetAlgoritmoDePropagacao

### NOT FOUND (404 on all tested patterns):
- /TodayCrossword/Get
- /DailyCrossword/Get
- /Crossword/GetDaily
- /Daily/Get
- /Event/GetDaily
- /DailyPassword/Get
- /Password/Get
- /Crossword/GetArchive
- /Crossword/GetAvailable
- /TodaysPassword/GetHistory
- /Player/GetData
- /Player/GetProfile
- /Player/GetStats
- /Progress/Get
- /Store/GetProducts
- /Achievement/GetList
- /Event/GetList
- /Daily/GetStatus
- Plus ~20 more patterns tested

## API ENDPOINTS (codydev.fulano.com.br - DEV API)
- Same endpoints as prod, same auth requirements
- /TodaysPassword/Get exists but needs auth
- No crossword endpoints found

## CDN / ADDRESSABLES
- CDN: addressables.codycross-game.com
- Catalog has 812K bytes of entries
- Only visual assets found: headers, characters, power-ups
- NO crossword/puzzle data in CDN catalog
- Daily crossword data is bundled in APK as addressable assets
- Asset keys format: tc_daily_en_YYYY_MM_DD_small, tc_daily_en_YYYY_MM_DD_midsize
- These are loaded dynamically by the app, not via API

## AUTH TOKEN
- App Token (hardcoded): 872fbb4c-fa3c-4534-b6e4-4b56bd7d3fc6
- Player Token: REQUIRED for /TodaysPassword/Get - comes from Google/Facebook login
- User is NOT logged in (logcat shows "No player ID found when refreshing")
- User needs to sign in via Google or Facebook in CodyCross app first

## DATA EXTRACTION APPROACHES - ALL TRIED AND FAILED

### ❌ ADB Shell Access to /data/data/
- USB ADB: uid=2000(shell) - cannot access /data/data/com.fanatee.cody/
- Wireless ADB: Failed to pair (protocol fault error on Windows)
- Shizuku ADB: Connection refused on localhost:5555 and 62001
- run-as: "package not debuggable"

### ❌ Shizuku Methods
- su -c: "inaccessible or not found" (phone is non-rooted, Shizuku doesn't provide su)
- shizuku command: not found in Termux
- termux-am broadcast to Shizuku: not tested yet (could try)
- Shizuku manages app shell permission: not granted to Termux yet

### ❌ ADB Backup
- Android 12+ blocks adb backup silently (549 bytes = header only, no popup shown)
- CMD: same result
- Phone needs to be unlocked + popup confirmed, but OS blocks it

### ❌ HTTP Proxy / MITM
- HTTP Toolkit: TLS error - CodyCross has certificate pinning
- Can't inject CA cert for API level 24+ apps without root
- Blocks app network after proxy setup

### ❌ PCAPdroid
- User says "we tried that already" (from old chat)
- Shows connection URLs but can't decrypt HTTPS content
- Can see destination domains but not request/response bodies

### ❌ Logcat
- Unity does NOT log its HTTP requests to logcat
- Only saw ad SDK traffic (AppLovin, Google Ads, Instagram)
- CleverTap accountId: W44-56Z-957Z accountToken: 165-440
- Google Play Games: "No player ID found" (not signed in)
- No game.codycross-game.com URLs in logcat at all
- debug.unity.log=1 didn't help

### ❌ tcpdump
- Not available on non-rooted phone

### ❌ Content Providers
- com.facebook.app.FacebookContentProvider1544814509142156: "No result found"

### ❌ Web Scraper
- Built fetcher/fetch_daily.py to scrape levelhacks.com
- USER EXPLICITLY REJECTED THIS: "dont make any web scraper man i want it to be done without that from main api end point"

### ❌ Frida Key Extraction
- emulator-extract.sh: Requires Android emulator + Frida - tested only in CI
- frida-extract.js: Hooks libil2cpp.so for AES key
- Potential AES key: 882jfme9zwejdkfi (not confirmed)
- Cannot run on physical phone without root

## KEY BLOCKERS
1. User is NOT logged into CodyCross → No player token → Can't call /TodaysPassword/Get
2. No root → Can't access /data/data/ for SharedPreferences or databases
3. Certificate pinning → Can't MITM to capture token
4. No daily crossword API endpoint → Data comes from encrypted .cody bundles in APK
5. Unity logcat silent → Can't see network requests
6. ADB backup blocked → Can't extract app data

## WHAT MIGHT STILL WORK

### 1. USER MUST LOGIN FIRST
- Open CodyCross → Profile → Sign in with Google/Facebook
- After login, try again with all methods
- The player token should appear in logcat or SharedPreferences after login

### 2. Shizuku App Shell Permission (NOT TESTED YET)
- Open Shizuku > 3-dot menu > "Manage app shell permission"
- Grant to Termux
- Then try: su -c "ls /data/data/com.fanatee.cody/shared_prefs/"
- Or: termux-am broadcast to moe.shizuku.privileged.api

### 3. MITM with SSL Key Logger (if login is done)
- Install PCAPdroid, set it up BEFORE opening CodyCross
- After login, the TLS handshake might leak session info
- Or use "Decrypt HTTPS" feature in PCAPdroid (requires Android 9-13, might work without root)

### 4. APK Reverse Engineering (offline)
- Extract the APK from /data/app/
- Use apktool to decompile
- Find the API URLs and authentication flow in smali/libil2cpp.so
- Use Il2CppDumper + Ghidra on libil2cpp.so to find AES key and API endpoints

### 5. Network Traffic on WiFi (passive capture)
- Use Wireshark on laptop, capture on same WiFi
- Can see DNS queries, TLS SNI (server names), packet sizes
- Won't get content but might see new endpoints

### 6. Try Shizuku's Binder Service Directly
- Shizuku provides IShellService via Android binder
- There might be a way to call it from Termux using app_process
- Not yet attempted

## APP PACKAGES / SDKs IN CODYCROSS
- Google Play Games (not signed in)
- Facebook SDK (login, sharing)
- Firebase (FCM push, analytics, logging)
- CleverTap (accountId: W44-56Z-957Z, accountToken: 165-440, region: us1)
- AppsFlyer (attribution)
- AppLovin/MAX (ads mediation - ms4.applvn.com, ms.applvn.com)
- Google AdMob (ads)
- IronSource (ads)
- Vungle (ads)
- BidMachine (ads)
- Unity Ads/Services
- okhttp (HTTP client)
- androidx.work (background tasks)
- androidx.browser/CustomTabs

## PHONE INFO
- Device: iQOO I2214
- Android version: likely 13-14
- CPU: arm64-v8a (MediaTek)
- Non-rooted
- Shizuku installed (running via wireless debugging)
- Wireless debugging port: dynamic (was 42863, changes on reboot)
- Termux installed from F-Droid
- USB ADB works (device serial: 10BD1R0CUG0005L)
