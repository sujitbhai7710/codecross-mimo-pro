# CodeCross Daily Answers 🧩

> Auto-updating website showing daily CodyCross puzzle answers, reverse-engineered from the official game API.

**Data Source:** CodyCross API (`codydev.fulano.com.br`) — no third-party scraping  
**Update Method:** Automated daily via GitHub Actions  
**Encryption:** AES-256-CBC (key extracted from app binary)

---

## Live Site

🌐 **[https://YOUR_USERNAME.github.io/codecross-mimo-pro/](https://YOUR_USERNAME.github.io/codecross-mimo-pro/)**

---

## How It Works

```
┌──────────────────────────────────────────────────────┐
│                    DAILY PIPELINE                     │
├──────────────────────────────────────────────────────┤
│                                                      │
│  1. GitHub Actions triggers at 00:05 UTC daily       │
│           │                                          │
│           ▼                                          │
│  2. Python script calls CodyCross API                │
│     GET /Puzzle/GetMundo?mundo=N&lang=en             │
│           │                                          │
│           ▼                                          │
│  3. API returns AES-256-CBC encrypted puzzle data    │
│     (2 records: metadata + puzzle content)           │
│           │                                          │
│           ▼                                          │
│  4. Script decrypts using key from app binary        │
│           │                                          │
│           ▼                                          │
│  5. Parsed answers saved to data/answers.json        │
│           │                                          │
│           ▼                                          │
│  6. Site auto-deploys to GitHub Pages                │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Project Structure

```
codecross-mimo-pro/
├── index.html                    # Today's answers page
├── archive.html                  # Past answers archive
├── styles.css                    # Dark theme styling
├── app.js                        # Client-side logic (auto-loading)
├── data/
│   └── answers.json              # Answer data (auto-updated)
├── fetcher/
│   └── fetch_answers.py          # API fetcher + decryption script
├── .github/workflows/
│   └── fetch-daily.yml           # GitHub Actions daily automation
├── REPORT.md                     # Full reverse engineering report
└── README.md                     # This file
```

## Pages

### Today (`index.html`)
- Shows current day's puzzle answers
- Auto-detects today's date and loads matching data
- Falls back to most recent entry if today's isn't available yet
- Shows data source status and last update time

### Archive (`archive.html`)
- Lists all past puzzle answers by date
- Search/filter by theme or date
- Click to expand and see full answer details
- Shows encrypted status for entries pending decryption

## Data Source

All data comes from the **official CodyCross API**, not from scraping third-party websites:

| Endpoint | Purpose | Encrypted? |
|----------|---------|------------|
| `GET /Puzzle/GetMundo` | Puzzle data (clues + answers) | ✅ AES-256-CBC |
| `GET /Texto/List` | UI text strings | ❌ Plain JSON |
| `GET /Player/GetPuzzleSettings` | Puzzle configuration | ❌ Plain JSON |

**API Base:** `https://codydev.fulano.com.br`  
**App Package:** `com.fanatee.cody` (v2.8.1)  
**Encryption:** AES-256-CBC with key from `libil2cpp.so`

## Auto-Update

The site uses **GitHub Actions** to automatically:

1. **Fetch** new puzzle data from the API every day at 00:05 UTC
2. **Decrypt** the AES-encrypted response using the extracted key
3. **Parse** puzzle clues and answers into JSON
4. **Commit** updated `data/answers.json` to the repo
5. **Deploy** the updated site to GitHub Pages

No manual intervention needed — the site stays current automatically.

## Setup

### 1. Fork/Clone
```bash
git clone https://github.com/YOUR_USERNAME/codecross-mimo-pro.git
cd codecross-mimo-pro
```

### 2. Enable GitHub Pages
- Go to repo Settings → Pages
- Set source to "GitHub Actions"

### 3. The automation handles the rest
- First run will happen at 00:05 UTC the next day
- Or trigger manually: Actions → "Fetch CodyCross Daily Answers" → Run workflow

### Manual Fetch (Local)
```bash
pip install pycryptodome
python fetcher/fetch_answers.py
```

## Reverse Engineering Details

See **[REPORT.md](REPORT.md)** for the full technical report including:
- APK structure analysis
- API endpoint discovery
- Encryption scheme details
- Binary analysis findings
- Decryption approach

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS (no frameworks)
- **Data Pipeline:** Python 3.11 + pycryptodome
- **Automation:** GitHub Actions (cron + deploy)
- **Hosting:** GitHub Pages (free)
- **Data Source:** CodyCross API (reverse-engineered)

## License

MIT — Educational purposes. Not affiliated with Fanatee.
