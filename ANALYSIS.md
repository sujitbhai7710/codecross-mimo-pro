# CodyCross APK Reverse Engineering Analysis

## Executive Summary

CodyCross (by Fanatee) is a Unity IL2CPP-compiled Android game. The daily puzzle content (including answers) is:
1. **Fetched from a backend API** as encrypted data
2. **Decrypted client-side** using RSA decryption (OAEP/v15 padding)
3. **Stored in Unity Addressable Assets** as encrypted `.cody` files

## APK Structure

```
CodyCross_2.8.1.xapk (240MB)
├── com.fanatee.cody.apk          # Main APK (base)
├── config.armeabi_v7a.apk        # ARM v7 native libs
├── config.arm64_v8a.apk          # ARM v8 native libs
├── UnityDataAssetPack.apk        # Game data (maps, puzzles)
├── AddressablesAssetPack.apk     # Addressable asset bundles
└── manifest.json                 # Package metadata
```

## Key Findings

### 1. API Endpoints Found

**Dev Server (still active):**
```
https://codydev.fulano.com.br/Puzzle/GetMundo?token=<UUID>&lang=<LANG_UUID>&mundo=<WORLD_NUM>&country=<COUNTRY>&dificuldadeDoPuzzle=<DIFFICULTY>&deviceType=Android&appVersion=<VERSION>
```

**Production API Domain:**
```
https://game.codycross-game.com/
```

**Content Catalog (Addressable Assets):**
```
https://addressables.codycross-game.com/Android/catalog_content_0.1.0.json
```

### 2. Data Flow Architecture

```
┌─────────────┐     HTTPS      ┌──────────────────┐
│  Android App │ ──────────────→│  Backend API      │
│  (Unity IL2CPP)│              │  (Fanatee Server) │
└──────┬──────┘                 └────────┬──────────┘
       │                                  │
       │  1. Fetch encrypted puzzle data  │
       │←─────────────────────────────────│
       │                                  │
       │  2. Decrypt with RSA private key │
       │     (PuzzleCrypto class)         │
       │                                  │
       │  3. Load from Addressable Assets │
       │     (.cody encrypted files)      │
       │                                  │
       │  4. Display puzzle + answers     │
       └──────────────────────────────────┘
```

### 3. Key Code Classes Found in Metadata

| Class | Purpose |
|-------|---------|
| `PuzzleService` | Main puzzle loading/syncing service |
| `PuzzleCrypto` / `PuzzleCryptoContent` | RSA decryption of puzzle data |
| `PuzzleSource` | Defines puzzle data source |
| `TodaysCrosswordDailyPuzzles` | Today's daily crossword data |
| `TcDailyPuzzles` | Daily puzzle container |
| `TcYearMonth` / `TcYearMonthProgresso` | Monthly puzzle tracking |
| `HttpCaller` | HTTP client for API calls |
| `ApiCaller` | API communication layer |
| `SyncContent` | Content synchronization |
| `PlayerService` | Player data and progress |
| `Fanatee.CodyCross.Domain` | Core domain models |

### 4. Encryption Details

The puzzle data uses **RSA encryption** with:
- `Decrypt_OAEP` - RSA OAEP padding
- `Decrypt_v15` - RSA PKCS#1 v1.5 padding  
- `DecryptValue` / `FinalDecrypt` - Low-level decryption
- `CreateDecryptor` - Symmetric decryptor creation

The dev API returns base64-encoded encrypted blob (verified - we successfully called the endpoint).

### 5. Puzzle Data Location

**Bundled encrypted files:**
```
assets/maps/mundo1.cody       (3.5MB - Android map data)
assets/maps/mundo1@1x.cody    (1.2MB - Android map data, 1x resolution)
assets/maps/mundo1-ios.cody   (3.7MB - iOS map data)
assets/maps/mundo1-ios@1x.cody (1.6MB - iOS, 1x resolution)
```

These `.cody` files are encrypted binary puzzle data that the game decrypts at runtime.

### 6. Language Support

The app supports 9 languages with dedicated content:
- English, Spanish, French, German, Italian
- Portuguese, Russian, Turkish, Dutch

Country-specific data is in `assets/country/{lang}.json`

## What Would Be Needed for Full Automation

### Option A: API Key Extraction (Easier)
1. Extract the API authentication token from the APK
2. Call the API endpoint directly
3. Decrypt the response using the extracted RSA private key
4. Parse the decrypted puzzle data

**Challenge:** The RSA private key is compiled into the IL2CPP binary and would require specialized tools (Il2CppDumper, Ghidra) to extract.

### Option B: Runtime Interception (Medium)
1. Use Frida/Xposed to hook the decryption functions at runtime
2. Capture decrypted puzzle data as it's processed
3. Save and serve the plaintext data

### Option C: Asset Decryption (Harder)
1. Extract the `.cody` files from the APK
2. Find the encryption key in the IL2CPP binary
3. Write a decryption tool
4. Parse the decrypted format

## Tool Requirements for Full RE

| Tool | Purpose |
|------|---------|
| `apktool` | APK decompilation |
| `jadx` | Java/Dex decompilation |
| `Il2CppDumper` | IL2CPP metadata extraction |
| `Ghidra` / `IDA Pro` | Binary analysis (native .so) |
| `Frida` | Runtime hooking |
| `UnityPy` | Unity asset extraction |

## Files in This Project

```
codecross-mimo-pro/
├── index.html              # Today's page
├── archive.html            # Archive page  
├── styles.css              # Dark theme CSS
├── app.js                  # Client logic
├── data/answers.json       # Answer data (manually populated)
├── ANALYSIS.md             # This file
├── README.md               # Project README
└── apk_extracted/          # Extracted APK contents (gitignored)
    ├── main_apk/           # Main APK decompiled
    ├── unitydata_apk/      # Unity data pack
    └── addressable_apk/    # Addressable assets
```

## Conclusion

The puzzle data flows through an encrypted API. To fully automate answer extraction:
1. The RSA private key needs to be extracted from the IL2CPP binary
2. Or runtime interception (Frida) can capture decrypted data
3. The `.cody` asset files are encrypted with a separate key

The website framework is ready - it just needs the data source connected to the decryption pipeline.
