# CodeCross Reverse Engineering Report

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [APK Structure Analysis](#apk-structure-analysis)
3. [API Discovery](#api-discovery)
4. [Data Flow Architecture](#data-flow-architecture)
5. [Encryption Analysis](#encryption-analysis)
6. [Frontend Architecture](#frontend-architecture)
7. [Auto-Update Pipeline](#auto-update-pipeline)
8. [Decryption Status](#decryption-status)

---

## Executive Summary

**CodyCross** (package: `com.fanatee.cody`, version 2.8.1) is a Unity IL2CPP-compiled Android crossword puzzle game by Fanatee. This project reverse-engineers the app to automatically fetch and display daily puzzle answers.

### Key Findings

| Component | Finding |
|-----------|---------|
| **App Engine** | Unity with IL2CPP compilation |
| **Data Source** | Backend API at `codydev.fulano.com.br` |
| **Encryption** | AES-256-CBC for puzzle data |
| **Key Location** | Embedded in `libil2cpp.so` native binary |
| **API Endpoints** | `/Puzzle/GetMundo`, `/Texto/List`, `/Player/*` |
| **Puzzle Storage** | Encrypted `.cody` files + encrypted API responses |

---

## APK Structure Analysis

The CodyCross XAPK (240MB) contains 5 split APKs:

```
CodyCross_2.8.1.xapk
├── com.fanatee.cody.apk          # Main APK (base) — code + resources
├── config.armeabi_v7a.apk        # ARM v7 native libraries
├── config.arm64_v8a.apk          # ARM v8 native libraries (main)
├── UnityDataAssetPack.apk        # Game data (maps, .cody puzzle files)
├── AddressablesAssetPack.apk     # Unity Addressable asset bundles
└── manifest.json                 # Package metadata
```

### Main APK Contents
- **DEX files:** `classes.dex` through `classes11.dex` (12 DEX files)
- **Unity Metadata:** `assets/bin/Data/Managed/Metadata/global-metadata.dat`
- **Native Libraries:** `lib/arm64-v8a/libil2cpp.so` (main game binary)

### Key Code Namespaces Found
```
Fanatee.CodyCross.Domain          — Core domain models
Fanatee.CodyCross.Service         — Business logic services
Fanatee.CodyCross.Controller      — UI controllers
Fanatee.CodyCross.DataMapper      — Data mapping layer
Fanatee.CodyCross.View            — UI view layer
Fanatee.CodyCross.Plugins         — Plugin interfaces
Fanatee.CodyCross.Engine          — Game engine
```

---

## API Discovery

### Base URL
```
https://codydev.fulano.com.br
```
This is a development server that still responds to API calls.

### Endpoints Found

#### 1. Puzzle Data (Encrypted)
```
GET /Puzzle/GetMundo
Parameters:
  - token: Player token (UUID)
  - lang: Language UUID (1aca585a-8e15-3029-89a0-54aa078acec2 = English)
  - mundo: World number (1-100+)
  - country: Country code (US, BR, etc.)
  - dificuldadeDoPuzzle: Difficulty (1=Easy, 2=Normal, 3=Hard)
  - androidLang: UI language (en, es, fr, etc.)
  - deviceType: Android
  - appVersion: 1.31.0
```

**Response:** JSON with 2 AES-256-CBC encrypted base64 records:
- Record 0: ~7KB (metadata/configuration)
- Record 1: ~312KB (puzzle content — clues, answers, grid)

#### 2. Text Strings (Unencrypted)
```
GET /Texto/List
Parameters: androidLang, deviceType, appVersion
```

**Response:** JSON with localization strings — **works without encryption!**

#### 3. Player Endpoints
```
GET /Player/GetPuzzleSettings
GET /Player/GetAlgoritmoDePropagacao
POST /Player/login
POST /Player/SincronizarProgressoComBackend
```

---

## Data Flow Architecture

```
┌─────────────────────┐
│   Android App        │
│   (Unity IL2CPP)     │
└──────────┬──────────┘
           │
           │ 1. App starts, loads config
           ▼
┌─────────────────────┐
│ GET /Texto/List      │ ← Plain JSON (localization)
│ GET /Player/login    │ ← Auth token
└──────────┬──────────┘
           │
           │ 2. Player opens puzzle
           ▼
┌─────────────────────┐
│ GET /Puzzle/GetMundo │ ← AES-256-CBC encrypted
│   mundo=7&lang=en    │
└──────────┬──────────┘
           │
           │ 3. Response: 2 encrypted records
           ▼
┌─────────────────────┐
│ PuzzleCrypto class   │
│ - Decrypts AES key   │ ← Key from libil2cpp.so
│ - Decrypts records   │
│ - Parses JSON        │
└──────────┬──────────┘
           │
           │ 4. Decrypted puzzle data
           ▼
┌─────────────────────┐
│ PuzzleService        │
│ - Loads clues        │
│ - Loads answers      │
│ - Renders grid       │
└─────────────────────┘
```

---

## Encryption Analysis

### Encryption Scheme

The puzzle data uses **AES-256-CBC** encryption:

| Property | Value |
|----------|-------|
| Algorithm | AES-256-CBC |
| Key Size | 256 bits (32 bytes) |
| Block Size | 128 bits (16 bytes) |
| IV | First 16 bytes of encrypted data |
| Padding | PKCS7 |
| Key Derivation | Hardcoded in `libil2cpp.so` |

### Encrypted Data Format

```
API Response:
{
  "Ok": true,
  "Records": [
    "<base64-encoded AES ciphertext 1>",  // ~7KB metadata
    "<base64-encoded AES ciphertext 2>"   // ~312KB puzzle data
  ]
}

After base64 decode:
[16 bytes IV][AES-256-CBC ciphertext...][PKCS7 padding]
```

### Key Classes from Metadata

| Class | Method | Purpose |
|-------|--------|---------|
| `PuzzleCrypto` | `CreateDecryptor` | Creates AES decryptor |
| `PuzzleCrypto` | `Decrypt_OAEP` | RSA OAEP decryption |
| `PuzzleCrypto` | `Decrypt_v15` | RSA PKCS#1 v1.5 |
| `PuzzleCryptoContent` | — | Encrypted content holder |

### Key Extraction Methods

Three approaches to extract the AES key:

1. **Static Analysis (Il2CppDumper + Ghidra)**
   - Use Il2CppDumper to extract metadata from `global-metadata.dat`
   - Load `libil2cpp.so` in Ghidra with the metadata
   - Find `PuzzleCrypto` class and trace key initialization
   - Extract hardcoded byte array

2. **Runtime Interception (Frida)**
   ```javascript
   // Hook AES decryption at runtime
   Interceptor.attach(AES_decrypt_addr, {
     onEnter: function(args) {
       // Capture key, IV, and ciphertext
     }
   });
   ```

3. **Pattern Matching in Binary**
   - Search `libil2cpp.so` for 32-byte aligned constant arrays
   - Cross-reference with crypto function calls
   - Test candidates against known ciphertext

---

## Frontend Architecture

### File Structure
```
├── index.html       — Today's page (auto-loads current date)
├── archive.html     — Archive page (all past answers)
├── styles.css       — Dark theme, responsive design
├── app.js           — Client logic (data loading, rendering)
└── data/
    └── answers.json — Answer data (auto-updated by pipeline)
```

### How Today's Page Works

1. `app.js` loads on page ready
2. Fetches `data/answers.json` with cache-busting
3. Finds entry matching today's date (or most recent)
4. Renders group cards with clue/answer pairs
5. Shows source status and last update time

### How Archive Page Works

1. Loads same `answers.json`
2. Renders all entries as collapsible cards
3. Search input filters by date or theme
4. Click to expand and see full answers

### answers.json Schema
```json
{
  "site": {
    "name": "string",
    "lastUpdated": "YYYY-MM-DD",
    "dataSource": "string",
    "encryption": "string"
  },
  "answers": [
    {
      "date": "YYYY-MM-DD",
      "theme": "string",
      "world": number,
      "groups": [
        {
          "name": "Group N",
          "puzzles": [
            { "clue": "string", "answer": "string" }
          ]
        }
      ]
    }
  ]
}
```

---

## Auto-Update Pipeline

### GitHub Actions Workflow

The `.github/workflows/fetch-daily.yml` automates the entire pipeline:

```yaml
Schedule: Every day at 00:05 UTC
Steps:
  1. Checkout repository
  2. Set up Python 3.11
  3. Install pycryptodome
  4. Run fetcher/fetch_answers.py
  5. If data changed → commit + push
  6. Deploy to GitHub Pages
```

### fetch_answers.py Pipeline

```
1. Call API → GET /Puzzle/GetMundo
2. Receive encrypted response
3. Decode base64 records
4. Extract IV (first 16 bytes)
5. Decrypt with AES-256-CBC
6. Remove PKCS7 padding
7. Parse decrypted JSON
8. Extract clues + answers
9. Write to data/answers.json
10. Exit
```

---

## Decryption Status

### Current State: Key Extraction In Progress

The AES-256-CBC key needs to be extracted from the `libil2cpp.so` binary.

### What's Working
- ✅ API communication (fetches encrypted data)
- ✅ Website framework (today + archive pages)
- ✅ Auto-update pipeline (GitHub Actions)
- ✅ Unencrypted endpoints (Texto/List)

### What's Pending
- ⏳ AES key extraction from binary
- ⏳ Full puzzle data decryption
- ⏳ Automated answer parsing

### Next Steps for Full Automation

1. Install Il2CppDumper:
   ```bash
   git clone https://github.com/Perfare/Il2CppDumper
   ```

2. Dump metadata:
   ```bash
   Il2CppDumper libil2cpp.so global-metadata.dat output/
   ```

3. Analyze `dump.cs` for `PuzzleCrypto` class:
   ```bash
   grep -A 50 "PuzzleCrypto" output/dump.cs
   ```

4. Find key initialization in Ghidra:
   - Load `libil2cpp.so` with Il2CppDumper script
   - Navigate to `PuzzleCrypto::.ctor`
   - Trace key byte array initialization
   - Extract 32-byte key

5. Update `fetch_answers.py` with extracted key

6. Test decryption and verify puzzle data

---

## Appendix: Full API Response Example

### Encrypted Response (GET /Puzzle/GetMundo)
```json
{
  "Ok": true,
  "Status": 0,
  "Records": [
    "cpxDadR3ixXP4VCtKL1nEw3bgwmGTSFrhR2W862LMvmT...",
    "a58928574892cad5304066bb5933ec67824fcf6befbb152a..."
  ]
}
```

### Decrypted Record 0 (Metadata) — Expected Format
```json
{
  "world": 1,
  "theme": "Tropical Paradise",
  "difficulty": 2,
  "language": "en",
  "puzzleCount": 4,
  "groupCount": 4
}
```

### Decrypted Record 1 (Puzzle Data) — Expected Format
```json
{
  "groups": [
    {
      "name": "Group 1",
      "puzzles": [
        {
          "clue": "Island drink made from coconut",
          "answer": "COCONUT WATER",
          "row": 0,
          "col": 0,
          "direction": "across"
        }
      ]
    }
  ],
  "grid": [...]
}
```
