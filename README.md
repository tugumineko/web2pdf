# Web2PDF-Crawler

> 🕷️ A depth-controlled recursive web crawler with high-fidelity PDF export, powered by Playwright.

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-green?logo=googlechrome)](https://playwright.dev/python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Depth-controlled Crawling** | Recursively discover links from a starting URL with configurable depth (default `1`). `depth=0` converts only the given page. |
| **Smart Link Deduplication** | URL normalization with fragment removal, `set`-based dedup, and protocol/domain filtering — no duplicates, no junk. |
| **Keyword Filtering** | `--url-contains` lets you keep only URLs matching specific keywords (e.g. `mc2`, `api`). |
| **High-Fidelity PDF via Playwright** | Headless Chromium renders modern JS-heavy pages faithfully, then exports pixel-perfect A4 PDFs with backgrounds. |
| **Multi-threaded Crawling** | `ThreadPoolExecutor` (8 workers) fetches and parses pages concurrently at the crawl stage. |
| **Async Concurrent PDF Export** | `asyncio.Semaphore`-controlled concurrency (default 8) converts multiple pages to PDF in parallel. |
| **Graceful Timeout Fallback** | If a page times out during navigation, the tool still attempts to export whatever has been rendered — no URL is silently lost. |
| **Smart File Naming** | PDF filenames are derived from page `<title>`, with automatic conflict resolution via numeric suffixes. |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Web Crawling | [`requests`](https://docs.python-requests.org/) + [`BeautifulSoup4`](https://www.crummy.com/software/BeautifulSoup/) |
| PDF Rendering | [`Playwright`](https://playwright.dev/python/) (Headless Chromium) |
| Concurrency (Crawl) | `concurrent.futures.ThreadPoolExecutor` |
| Concurrency (PDF) | `asyncio` + `asyncio.Semaphore` |
| CLI | `argparse` |

---

## 🚀 Quick Start

### 1. Clone

```bash
git clone https://github.com/tugumineko/web2pdf.git
cd web2pdf
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Run

```bash
# Basic: crawl depth=1, same-domain links → PDF
python -u crawl_and_convert.py "https://example.com/docs/"

# Single page only (depth=0)
python -u crawl_and_convert.py "https://example.com/page" --depth 0

# Filter URLs containing keywords
python -u crawl_and_convert.py "https://example.com/docs/" --url-contains api guide

# Custom output directory & concurrency
python -u crawl_and_convert.py "https://example.com/" --output "./my_pdfs" --concurrency 4

# Include external domain links
python -u crawl_and_convert.py "https://example.com/" --include-external --depth 2
```

---

## 📖 CLI Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `url` *(positional)* | — | Starting URL to crawl |
| `--depth N` | `1` | Recursive crawl depth. `0` = start URL only |
| `--output DIR` | `output_pdfs` | Output directory for PDFs |
| `--include-external` | off | Also crawl links to other domains |
| `--url-contains K1 K2 …` | *(none)* | Only keep URLs containing **any** of the given keywords |
| `--concurrency N` | `8` | Number of parallel Playwright pages for PDF conversion |

---

## 📂 Project Structure

```
web2pdf/
├── crawl_and_convert.py   # Main script — crawler + PDF converter
├── requirements.txt       # Python dependencies
├── AGENT.md               # AI collaboration & maintenance log
└── README.md              # This file
```

---

## 🔄 Pipeline Overview

```
Start URL
    │
    ▼
┌─────────────────────────────┐
│  1. Crawl (ThreadPool × 8)  │  BFS by depth level
│     requests + BeautifulSoup│  protocol / domain / keyword filter
│     normalize + dedup (set) │
└─────────────┬───────────────┘
              │ filtered URL list
              ▼
┌─────────────────────────────┐
│  2. Convert (async × N)     │  Playwright headless Chromium
│     domcontentloaded → PDF  │  timeout fallback export
│     title-based naming      │  conflict auto-suffix
└─────────────┬───────────────┘
              │
              ▼
         PDF files  →  output directory
```

---

## ⚠️ Error Handling

- **Network failures** (timeout, 4xx/5xx, connection refused): logged and skipped — never blocks the pipeline.
- **Page load timeout**: falls back to exporting whatever has been rendered so far.
- **Non-HTML content**: silently skipped during crawl.
- All errors are reported in the final summary.

---

## 📝 License

[MIT](LICENSE) — free for personal and commercial use.

---

## 🤝 Contributing

Issues and PRs are welcome. See [AGENT.md](AGENT.md) for the AI collaboration log and future roadmap.
