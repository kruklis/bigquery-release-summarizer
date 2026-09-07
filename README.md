# BigQuery Release Intelligence 🚀

An automated ingestion, synthesis, and intelligence engine for Google Cloud BigQuery release notes. Built for Google Cloud Engineers (CEs), Solutions Architects, DBAs, and Data Engineering leads.

![BigQuery Release Intelligence](https://img.shields.io/badge/Google%20Cloud-BigQuery-4285F4?style=flat-square&logo=googlecloud&logoColor=white)
![Google Antigravity](https://img.shields.io/badge/Antigravity-CLI%20Enabled-34A853?style=flat-square)
![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20External%20Pip-blueviolet?style=flat-square)
![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=flat-square)

---

## Highlights

- 📡 **Live Atom XML Ingestion**: Directly ingests the official Google Cloud BigQuery Atom feed (`https://cloud.google.com/feeds/bigquery-release-notes.xml`) with local caching and TTL management.
- 🏷️ **Granular Item Breakdown**: Parses release drops into structured items tagged by category (`Feature`, `Change`, `Fixed`, `Security`, `Announcement`, `Deprecated`) and launch stage (`GA` vs `Preview`).
- 🧠 **Dual Summarization Engine**:
  - **Google Antigravity AI (`agy -p`)**: Synthesizes releases into Executive Briefs, Technical Architecture & Migration Guides, Changelog Digests, or ad-hoc custom architecture queries.
  - **Analytical Rule Engine**: Instant offline fallback clustering updates by thematic area (AI/ML, SQL Modeling, Drivers, FinOps).
- 🖥️ **Interactive Web Dashboard**: Premium dark-mode interface with glassmorphic accents, real-time KPI metrics, search, filtering, and one-click Markdown copy/export.
- ⚡ **Full-Featured CLI**: Query, summarize, inspect stats, or launch the web server directly from terminal.
- 📦 **Zero External Dependencies**: Built entirely with Python 3 standard libraries and vanilla HTML5/CSS3/ES6.

---

## Quick Start

### 1. Requirements
- Python 3.10+
- (Optional for AI synthesis) [Google Antigravity CLI](https://cloud.google.com) (`agy`) installed and in PATH. If `agy` is not present, the app seamlessly uses its built-in analytical engine.

### 2. Run the Web Dashboard
```bash
python3 main.py --serve --port 8080
```
Open your browser at [http://localhost:8080](http://localhost:8080).

---

## CLI Usage

### View Summary Statistics
```bash
python3 main.py --stats
```

### Fetch Recent Updates
```bash
# Fetch updates from the last 14 days
python3 main.py --fetch --days 14

# Filter by category or stage
python3 main.py --fetch --days 30 --stage GA --category Feature

# Search by keyword
python3 main.py --fetch --search "JDBC"
```

### Generate AI Summaries
```bash
# Executive briefing (Last 30 days)
python3 main.py --summarize --days 30 --mode executive

# Technical architecture & migration guide
python3 main.py --summarize --days 30 --mode architect

# Changelog digest with export to Markdown
python3 main.py --summarize --days 14 --mode digest --export digest.md

# Ask custom architecture questions
python3 main.py --summarize --query "What are the new capabilities for tabular foundation models and TabFM?"

# Offline analytical mode (no LLM call required)
python3 main.py --summarize --days 30 --offline
```

---

## Project Structure

```
bigquery-release-summarizer/
├── fetcher.py        # Atom XML feed fetcher, parser & item-level caching
├── summarizer.py     # AI summarizer (via agy CLI) & analytical rule fallback
├── server.py         # Zero-dependency Python HTTP server & REST API
├── main.py           # Unified CLI entrypoint and server runner
├── cache/            # Local JSON cache directory
│   └── release_notes.json
└── web/              # Responsive Web Dashboard
    ├── index.html    # Semantic layout, KPI cards, AI Studio & timeline
    ├── style.css     # Google Cloud dark theme, glassmorphism & typography
    └── app.js        # Dynamic filtering, API integration & Markdown renderer
```

---

## REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status |
| `GET` | `/api/stats` | Aggregate release metrics by category & stage |
| `GET` | `/api/notes` | Query filtered items (`days`, `category`, `stage`, `search`) |
| `POST` | `/api/summarize` | Generate AI or analytical summary report |
| `POST` | `/api/refresh` | Force invalidation of cache and re-fetch from GCP |

---

## License

Apache License 2.0. See `LICENSE` for details.
