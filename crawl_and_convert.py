import argparse
import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, async_playwright


REQUEST_TIMEOUT = 10
NAV_TIMEOUT_MS = 120000
CRAWL_WORKERS = 8
PDF_CONCURRENCY = 8


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_url(url: str) -> str:
    clean, _ = urldefrag(url.strip())
    return clean


def sanitize_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:140] or "untitled"


def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.netloc}{parsed.path}".strip("/")
    base = base.replace("/", "_")
    return sanitize_filename(base or parsed.netloc or "page")


def _fetch_and_extract(session: requests.Session, url: str, start_netloc: str,
                       same_domain_only: bool) -> Tuple[str, List[str]]:
    """并行抓取单个页面并提取链接，返回 (源URL, [提取到的链接])。"""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return url, []

    ct = resp.headers.get("Content-Type", "")
    if "html" not in ct.lower():
        return url, []

    soup = BeautifulSoup(resp.text, "html.parser")
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        abs_url = normalize_url(urljoin(url, a["href"]))
        if not is_http_url(abs_url):
            continue
        if same_domain_only and urlparse(abs_url).netloc != start_netloc:
            continue
        links.append(abs_url)
    return url, links


def crawl_links(start_url: str, max_depth: int, same_domain_only: bool = True) -> List[str]:
    if not is_http_url(start_url):
        raise ValueError(f"无效URL: {start_url}")

    start_norm = normalize_url(start_url)
    start_netloc = urlparse(start_url).netloc
    collected: Set[str] = {start_norm}
    visited: Set[str] = set()

    print(f"[Crawler] 起始: {start_url} | 深度: {max_depth}")

    # depth=0: 仅转换起始URL，不做任何网络请求
    if max_depth == 0:
        return [start_norm]

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    current_level: List[Tuple[str, int]] = [(start_norm, 0)]

    while current_level:
        # 过滤已访问
        to_fetch = [(u, d) for u, d in current_level if u not in visited]
        if not to_fetch:
            break

        for u, _ in to_fetch:
            visited.add(u)

        # 仅对 depth < max_depth 的页面做链接提取
        fetch_for_links = [(u, d) for u, d in to_fetch if d < max_depth]
        next_level: List[Tuple[str, int]] = []

        if fetch_for_links:
            with ThreadPoolExecutor(max_workers=CRAWL_WORKERS) as executor:
                futures = {
                    executor.submit(_fetch_and_extract, session, u, start_netloc, same_domain_only): (u, d)
                    for u, d in fetch_for_links
                }
                for future in as_completed(futures):
                    src_url, depth = futures[future]
                    _, found = future.result()
                    new_count = 0
                    for link in found:
                        if link not in collected:
                            collected.add(link)
                            new_count += 1
                        if link not in visited:
                            next_level.append((link, depth + 1))
                    if new_count:
                        print(f"  {src_url} -> +{new_count} 新链接")

        current_level = next_level

    print(f"[Crawler] 完成, 共 {len(collected)} 个唯一URL")
    return sorted(collected)


async def convert_urls_to_pdf(urls: List[str], output_dir: Path,
                              concurrency: int = PDF_CONCURRENCY) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, str] = {}
    used_names: Set[str] = set()
    name_lock = asyncio.Lock()
    total = len(urls)

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        semaphore = asyncio.Semaphore(concurrency)

        async def _convert_one(index: int, url: str):
            async with semaphore:
                page = await browser.new_page()
                try:
                    timed_out = False
                    resp = None
                    try:
                        resp = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    except PlaywrightTimeoutError:
                        timed_out = True

                    if resp and resp.status >= 400:
                        print(f"[PDF] ({index}/{total}) HTTP {resp.status}: {url}")

                    title = (await page.title()).strip()
                    base_name = sanitize_filename(title) if title else url_to_filename(url)

                    async with name_lock:
                        final_name = base_name
                        suffix = 2
                        while final_name.lower() in used_names:
                            final_name = f"{base_name}_{suffix}"
                            suffix += 1
                        used_names.add(final_name.lower())

                    pdf_path = output_dir / f"{final_name}.pdf"
                    await page.pdf(path=str(pdf_path), format="A4", print_background=True)
                    results[url] = str(pdf_path)
                    tag = " (超时回退)" if timed_out else ""
                    print(f"[PDF] ({index}/{total}) OK{tag}: {pdf_path.name}")

                except (PlaywrightError, Exception) as exc:
                    print(f"[PDF] ({index}/{total}) FAIL: {url} -> {exc}")
                finally:
                    await page.close()

        tasks = [_convert_one(i, url) for i, url in enumerate(urls, 1)]
        await asyncio.gather(*tasks)
        await browser.close()

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="递归抓取网页链接并批量转换为PDF（Playwright）"
    )
    parser.add_argument("url", help="起始网页URL")
    parser.add_argument("--depth", type=int, default=1, help="递归深度，默认1")
    parser.add_argument(
        "--output",
        default="output_pdfs",
        help="PDF输出目录，默认 output_pdfs",
    )
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="包含外部域名链接（默认不包含）",
    )
    parser.add_argument(
        "--url-contains",
        nargs="+",
        default=[],
        help="仅保留URL中包含指定关键词的链接",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=PDF_CONCURRENCY,
        help=f"PDF并发转换数，默认 {PDF_CONCURRENCY}",
    )
    return parser.parse_args()


def filter_urls_by_keywords(urls: List[str], keywords: List[str]) -> List[str]:
    normalized_keywords = [k.lower().strip() for k in keywords if k.strip()]
    if not normalized_keywords:
        return urls
    return [u for u in urls if any(k in u.lower() for k in normalized_keywords)]


async def async_main() -> None:
    args = parse_args()
    start_url = normalize_url(args.url)
    output_dir = Path(args.output)

    if args.depth < 0:
        raise ValueError("depth 不能为负数")

    t0 = time.perf_counter()

    urls = crawl_links(start_url, args.depth, same_domain_only=not args.include_external)
    urls = filter_urls_by_keywords(urls, args.url_contains)

    print(f"[Main] 过滤后URL数: {len(urls)}")
    if urls:
        for u in urls:
            print(f"  -> {u}")

    if not urls:
        print("[Main] 无可转换URL，结束。")
        return

    results = await convert_urls_to_pdf(urls, output_dir, concurrency=args.concurrency)

    elapsed = time.perf_counter() - t0
    print(f"\n{'=' * 60}")
    print(f"[Summary] 成功: {len(results)}/{len(urls)} | 耗时: {elapsed:.1f}s")
    print(f"[Summary] 输出: {output_dir.resolve()}")
    for src, pdf in results.items():
        print(f"  {src} -> {Path(pdf).name}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(async_main())
