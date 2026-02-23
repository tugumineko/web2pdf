# AGENT.md — AI Collaboration & Maintenance Log

> This project was co-developed by a **human developer** and an **AI Agent** (GitHub Copilot, Claude Opus 4.6).  
> This document records the Agent's contributions, design decisions, and future roadmap.

---

## 🤖 Role Definition

| Role | Responsibility |
|------|---------------|
| **Human Developer** | Project conception, requirements specification, use-case validation, final QA |
| **AI Agent** | Architecture design, full implementation, performance optimization, testing, documentation |

---

## 📋 Agent Optimization Log

### Phase 1 — Initial Implementation
- Built the end-to-end pipeline: recursive BFS crawler → URL dedup/filter → Playwright PDF export.
- Implemented `depth` semantics: `depth=0` returns only the start URL with zero network overhead; `depth=N` does level-by-level BFS up to N.
- Designed a 3-stage URL filter chain: **protocol → domain → keyword**, ensuring correct order of operations.
- Added `urldefrag()` normalization + `set`-based dedup to eliminate fragment-only duplicates.
- Implemented smart PDF filename derivation from `<title>` with automatic `_N` suffix for conflicts.

### Phase 2 — Performance Overhaul
Key bottleneck analysis & fixes:

| Before | After | Improvement |
|--------|-------|-------------|
| Serial `requests` crawl (1 page at a time) | `ThreadPoolExecutor` with 8 workers, level-parallel BFS | **~5–8× faster crawl** |
| Serial PDF conversion (1 page at a time) | `asyncio.Semaphore`-controlled concurrent Playwright pages (default 8) | **~4–8× faster export** |
| `networkidle` wait (extra 8s/page) | Removed — `domcontentloaded` is sufficient for PDF | **Saved ~8s per page** |
| Navigation timeout 60s | Reduced to 30s (later tuned to 120s for slow sites) | Balanced speed vs. reliability |
| Verbose logs ("跳过提取", "非HTML内容") | Only relevant output: new links found, conversion progress, final summary | **Clean console** |

### Phase 3 — Edge Cases & Robustness
- **Timeout fallback**: if `page.goto()` times out, the page snapshot is still exported as PDF instead of being skipped.
- **HTTP 4xx/5xx**: logged with status code but not fatal — pipeline continues.
- **Non-HTML content**: silently skipped during crawl (no noise).
- **Filename sanitization**: Windows-illegal characters (`\/:*?"<>|`) replaced; length capped at 140 chars.
- **`asyncio.Lock`** for `used_names` set to prevent race conditions in concurrent PDF naming.

---

## 🏗️ Architecture Decisions

### Why Playwright over win32com/IE?
- `win32com` + IE/Word engine only works on Windows with Office installed — not portable.
- IE engine cannot render modern JS frameworks (React, Vue, etc.).
- Playwright headless Chromium gives browser-grade rendering fidelity on any OS with zero external dependencies.
- Native `page.pdf()` API produces production-quality A4 output with backgrounds.

### Why ThreadPoolExecutor for crawling + asyncio for PDF?
- Crawl stage is I/O-bound HTTP (many small requests) — threads are simple and efficient.
- PDF stage needs Playwright's async API — `asyncio.gather` + Semaphore gives clean concurrency control without thread-safety headaches on the browser instance.

---

## 🔧 Behavioral Contracts (for future Agents)

1. **`depth=0` semantics**: Only convert the start URL itself; do NOT extract links from the page.
2. **URL filter order**: Protocol → Domain → Keyword. Always in this order.
3. **Dedup**: `set` + `urldefrag`. Normalize before inserting.
4. **Naming**: `<title>` first → URL-derived fallback → `_N` suffix for conflicts.
5. **Error policy**: Log and skip. Never abort the pipeline for a single URL failure.
6. **Agent discipline**:
   - Read current file state before editing — never blindly overwrite.
   - Prefer minimal diffs — don't refactor unrelated code.
   - Run at least one target-scenario test after every code change.
   - On `KeyboardInterrupt` / long hang: diagnose, lower wait conditions, enable fallback export.

---

## 🧪 Recommended Test Cases

### 1. Single page (depth=0)
```powershell
python -u crawl_and_convert.py "https://wolfand11.github.io/blogs/animation/MagicaCloth2.html" --depth 0
```
Expected: 1 URL → 1 PDF.

### 2. Keyword filter
```powershell
python -u crawl_and_convert.py "https://magicasoft.jp/en/mc2_about/" --depth 1 --url-contains mc2
```
Expected: Only URLs containing `mc2` are converted.

### 3. Full recursive (same-domain)
```powershell
python -u crawl_and_convert.py "https://magicasoft.jp/en/mc2_about/" --depth 1
```
Expected: Same-domain links only, deduped, batch PDF export.

---

## 🚀 Future Roadmap

| Priority | Enhancement | Notes |
|----------|-------------|-------|
| 🔴 High | **Incremental / resume support** | Skip URLs whose PDFs already exist in the output dir; add `--force` to override |
| 🔴 High | **Sitemap.xml support** | Parse `sitemap.xml` as an alternative link source — faster and more complete than HTML crawling |
| 🟡 Medium | **Export format options** | Support `--format png/html/mhtml` in addition to PDF |
| 🟡 Medium | **Configurable page settings** | Paper size, margins, header/footer, landscape mode via CLI flags |
| 🟡 Medium | **Anti-bot evasion** | Rotate User-Agents, respect `robots.txt`, add request delays (`--delay`) |
| 🟢 Low | **Web UI / TUI dashboard** | Real-time progress with `rich` or a lightweight Flask frontend |
| 🟢 Low | **Docker image** | One-command deployment with Playwright pre-installed |
| 🟢 Low | **URL exclude patterns** | `--url-excludes` to blacklist certain paths (e.g. `/tag/`, `/page/`) |

---

## 📊 Proven Results

Tested on `https://magicasoft.jp/en/mc2_about/` with `--depth 1 --url-contains mc2`:

- **147** same-domain URLs discovered
- **71** URLs matched keyword filter
- **71/71** PDFs exported successfully
- Total runtime: **~520s** (with 8 concurrent Playwright pages)

---

*Last updated: 2026-02-23 by AI Agent (GitHub Copilot / Claude Opus 4.6)*
