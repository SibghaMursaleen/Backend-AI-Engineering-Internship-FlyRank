<h1 align="center">🔷 Polite Web Scraper</h1>

<p align="center">
  A compliant, professional Python scraper that builds a structured backend glossary database by crawling Wikipedia under strict robots.txt compliance and rate limiting.<br/>
  Your gathered data serves as a clean, structured corpus for building a RAG search pipeline.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Parser-BeautifulSoup%204-F7DF1E?style=for-the-badge&logo=python&logoColor=black"/>
  <img src="https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>
</p>

---

## 📌 Overview

The **Polite Web Scraper** is a production-ready data-gathering application that fetches technical articles from Wikipedia, parses section-by-section contents, cleans citation footnotes, and structures the records into a local SQLite database. It is designed to act as an exemplary web bot by respecting site rules, preventing server overload, and identifying itself cleanly.

> **Key:** This scraper programmatically parses the target domain's `robots.txt` rules using `urllib.robotparser` and uses those settings to regulate its actions.

---

## ⚙️ How It Works

| Step | Stage | Description |
|------|-------|-------------|
| 1 | **Robots.txt Check** | Queries and parses the domain's `robots.txt` file to ensure the crawler is permitted to fetch the specified path. |
| 2 | **Identify & Fetch** | Issues an HTTP GET request with a custom **User-Agent** header containing contact info, using retries and timeouts for network resilience. |
| 3 | **Parse & Extract** | Isolates the main parser output, decomposes sidebars/tables/toc boxes, and parses the introduction paragraph and sub-headings. |
| 4 | **Clean Content** | Removes citation bracket numbers (e.g. `[1]`) and strips extra formatting, leaving only clean plain-text. |
| 5 | **Structure & Save** | Inserts the concepts and sections transactionally into the local SQLite database. |
| 6 | **Paced Crawling** | Reads the `Crawl-delay` directive from `robots.txt` or falls back to a custom configuration to sleep between crawls. |

---

## 📁 Project Structure

```
Polite Web Scraper/
│
├── app/
│   ├── __init__.py      # Package initialization
│   ├── config.py        # Environment loader and seed configurations
│   ├── database.py      # SQLite table initialization and operations
│   ├── robots.py        # robots.txt parsed rules and cache manager
│   └── scraper.py       # Fetching, BeautifulSoup parsing, cleaning, and pacing loop
│
├── .env.example         # Template for environment settings
├── .env                 # Local variables (User-Agent, delays, DB filename)
├── main.py              # Interactive console dashboard application
├── requirements.txt     # Python external package dependencies
└── README.md            # Project description and user guide
```

> **Note:** The `.env` file containing local configurations should not be committed to source control. Generate it by copying `.env.example`.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3** installed on your system.
- External dependencies listed in `requirements.txt`.

### Step 1: Install Dependencies
Open your shell and run the installer command:
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy the configuration template to create your local variables:
```bash
cp .env.example .env
```
Ensure you update the `USER_AGENT` parameter inside `.env` to specify your email address.

### Step 3: Launch CLI Dashboard
Run the interactive CLI dashboard:
```bash
python main.py
```

| Key / Option | Action |
|--------------|--------|
| `1` | Run Scraper to fetch Wikipedia glossary pages |
| `2` | Search and read scraped glossary concepts and subsections |
| `3` | View statistics (counts of records) in SQLite DB |
| `4` | Test compliance of any URL against its target `robots.txt` |
| `5` | Exit the CLI application |

---

## 🎨 Configuration Options

| Environment Variable | Default Value | Description | Status |
|----------------------|---------------|-------------|--------|
| `USER_AGENT` | `BackendInternScraper/1.0 (+mailto:...)` | Header string that identifies the scraper bot to the server. | ✅ Active |
| `DEFAULT_DELAY` | `2.0` | Default seconds to sleep between page fetches if not specified by `robots.txt`. | ✅ Active |
| `DATABASE_PATH` | `wiki_backend_glossary.db` | Local SQLite database file location inside project. | ✅ Active |

---

## 🛠️ Tech Stack

| Technology | Role |
|------------|------|
| **Python 3** | Implementation language of the entire scraper system. |
| **BeautifulSoup 4** | HTML parsing and navigation library to extract structured divs and sections. |
| **SQLite** | Lightweight database engine used to save data transactionally. |
| **Requests** | Synchronous HTTP client library handling timeouts and status codes. |
| **Python-Dotenv** | Parses and loads settings from `.env` configuration file. |

---

## ⚠️ Tips / Best Practices

- **Respect Status Codes**: If you get a `429 Too Many Requests` code, sleep for a few seconds (or check the `Retry-After` header) before trying again to avoid getting permanently blocked.
- **Run Incremental Scrapes**: Keep track of what you have crawled in the database. Don't fetch the same pages again unless explicitly requested.
- **Save Structured Content**: Store text section-by-section so that next week's RAG system can easily fetch relevant paragraphs instead of having to search massive documents.

---

## 📄 License

This project is released under the [MIT License](LICENSE) — free to use, modify, and distribute.

---

<p align="center">
  Built with 🐍 Python &nbsp;·&nbsp; Data collection done professionally
</p>
