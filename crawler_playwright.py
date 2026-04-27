"""
crawler.py — Web news crawler using Playwright
"""

import asyncio
import json
import os
import re
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
INPUT_FILE     = Path(r"C:/PYTHON/.entree/SitesSources/sites_actus_labos.txt")
OUTPUT_DIR     = Path(r"C:/PYTHON/.data/Resultatscrawling")
JOURNAL_FILE   = Path(r"C:/PYTHON/.data/Resultatscrawling/journal.json")
DELAY_MIN      = 2.0    # secondes, délai minimum entre deux requêtes
DELAY_MAX      = 5.0    # secondes, délai maximum entre deux requêtes
MAX_DEPTH      = 1
RESPECT_ROBOTS     = True
HEADLESS           = False  # navigateur visible pour résoudre les anti-bots manuellement
CURRENT_YEAR_ONLY  = True   # ne retenir que les articles de l'année en cours
SAVE_IF_NO_DATE    = False  # sauvegarder si aucune date n'est détectable

EXCLUDED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".avi", ".zip", ".tar", ".gz", ".exe",
    ".css", ".js", ".xml", ".json", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".rss",
}

EXCLUDED_PATH_PATTERNS = [
    r"/tag/", r"/tags/", r"/author/", r"/auteur/", r"/category/",
    r"/categorie/", r"/page/\d+/?$", r"/feed/?$", r"/rss/?$",
    r"/search[/?]", r"/login", r"/register", r"/cart", r"/panier",
    r"/account/", r"/cdn-cgi/", r"[?&]s=", r"[?&]p=\d+$",
]

ANTIBOT_SIGNALS = [
    "cf-browser-verification", "challenge-form", "cf_chl_opt",
    "access denied", "attention required",
    "enable javascript and cookies",
    "please verify you are a human",
    "ddos protection by cloudflare",
    "please complete the security check",
    "just a moment",
]

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL
# ─────────────────────────────────────────────────────────────────────────────
def load_journal() -> dict:
    if Path(JOURNAL_FILE).exists():
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_journal(journal: dict):
    with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=2)

def clear_journal():
    if Path(JOURNAL_FILE).exists():
        os.remove(JOURNAL_FILE)
        log("Journal vidé.")

# ─────────────────────────────────────────────────────────────────────────────
# URL UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def load_input_urls() -> list[str]:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def normalize_url(url: str) -> str:
    return url.split("#")[0].rstrip("/")

def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()

def is_same_domain(url: str, base_domain: str) -> bool:
    host = get_domain(url).removeprefix("www.")
    base = base_domain.lower().removeprefix("www.")
    return host == base

def is_html_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    for ext in EXCLUDED_EXTENSIONS:
        if path.endswith(ext):
            return False
    for pattern in EXCLUDED_PATH_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    return True

def generate_filename(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    path   = parsed.path.strip("/").replace("/", "__")
    query  = re.sub(r"[^\w]", "_", parsed.query)[:40] if parsed.query else ""

    parts = [domain]
    if path:
        parts.append(path)
    if query:
        parts.append(query)

    name = "__".join(parts)
    name = re.sub(r"[^\w\-_.]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:180] + ".html"

# ─────────────────────────────────────────────────────────────────────────────
# ROBOTS.TXT
# ─────────────────────────────────────────────────────────────────────────────
_robots_cache: dict = {}

def is_allowed_by_robots(url: str) -> bool:
    if not RESPECT_ROBOTS:
        return True
    parsed     = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    if robots_url not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            _robots_cache[robots_url] = rp
        except Exception:
            _robots_cache[robots_url] = None
    rp = _robots_cache[robots_url]
    return rp.can_fetch("*", url) if rp else True

# ─────────────────────────────────────────────────────────────────────────────
# ANTI-BOT
# ─────────────────────────────────────────────────────────────────────────────
async def detect_antibot(page) -> bool:
    try:
        content = (await page.content()).lower()
        title   = (await page.title()).lower()
        return any(s in content or s in title for s in ANTIBOT_SIGNALS)
    except Exception:
        return False

async def wait_for_human():
    log("ANTI-BOT DETECTE — Résolvez le challenge dans le navigateur.")
    log("Appuyez sur Entrée pour continuer...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input)

# ─────────────────────────────────────────────────────────────────────────────
# DATE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
def _parse_year(value: str) -> int | None:
    m = re.search(r"\b(20\d{2})\b", str(value))
    return int(m.group(1)) if m else None

def extract_article_year(html: str, url: str) -> int | None:
    soup = BeautifulSoup(html, "lxml")

    # JSON-LD datePublished / dateCreated
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            for key in ("datePublished", "dateCreated", "dateModified"):
                if data.get(key):
                    year = _parse_year(data[key])
                    if year:
                        return year
        except Exception:
            pass

    # OpenGraph article:published_time
    og = soup.find("meta", property="article:published_time")
    if og:
        year = _parse_year(og.get("content", ""))
        if year:
            return year

    # Meta tags standards
    for name in ("date", "pubdate", "publish_date", "DC.date",
                 "article.published", "article:published_time"):
        meta = soup.find("meta", attrs={"name": name})
        if meta:
            year = _parse_year(meta.get("content", ""))
            if year:
                return year

    # <time datetime="...">
    time_el = soup.find("time", attrs={"datetime": True})
    if time_el:
        year = _parse_year(time_el["datetime"])
        if year:
            return year

    # Pattern dans l'URL : /2026/ ou /2026-04
    m = re.search(r"/(20\d{2})[/\-]", url)
    if m:
        return int(m.group(1))

    return None

def is_current_year(html: str, url: str) -> bool:
    """Retourne True si l'article est de l'année en cours, ou si la date est indéterminée."""
    if not CURRENT_YEAR_ONLY:
        return True
    year = extract_article_year(html, url)
    if year is None:
        return SAVE_IF_NO_DATE
    return year == datetime.now().year

# ─────────────────────────────────────────────────────────────────────────────
# NEWS PAGE DETECTION
# ─────────────────────────────────────────────────────────────────────────────
_DATE_CLASS   = re.compile(r"\bdate\b|pubdate|published|timestamp|posted", re.I)
_AUTHOR_CLASS = re.compile(r"\bauthor\b|byline|auteur", re.I)
_BODY_CLASS   = re.compile(r"article.?body|post.?content|entry.?content|article.?content|article.?text", re.I)

def is_news_page(html: str) -> bool:
    soup  = BeautifulSoup(html, "lxml")
    score = 0

    # JSON-LD schema.org
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data  = json.loads(script.string or "")
            types = data.get("@type", "")
            if isinstance(types, list):
                types = " ".join(types)
            if any(t in types for t in ["NewsArticle", "Article", "BlogPosting", "ReportageNewsArticle"]):
                score += 4
        except Exception:
            pass

    # OpenGraph
    og = soup.find("meta", property="og:type")
    if og and "article" in og.get("content", "").lower():
        score += 3

    # Semantic HTML
    if soup.find("article"):
        score += 2
    if soup.find("time") or soup.find(class_=_DATE_CLASS):
        score += 2
    if soup.find(rel="author") or soup.find(class_=_AUTHOR_CLASS):
        score += 1
    if soup.find("meta", attrs={"name": "author"}):
        score += 1
    if soup.find(class_=_BODY_CLASS):
        score += 2

    return score >= 3

# ─────────────────────────────────────────────────────────────────────────────
# LINK EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
_NAV_JS = """
els => {
    function isNav(el) {
        while (el && el.tagName) {
            const tag = el.tagName.toLowerCase();
            if (['nav', 'header', 'aside', 'footer'].includes(tag)) return true;
            const token = ((el.className || '').toString() + ' ' + (el.id || '')).toLowerCase();
            if (/\\b(nav|navbar|navigation|menu|sidebar|breadcrumb|toc|table-of-contents)\\b/.test(token)) return true;
            el = el.parentElement;
        }
        return false;
    }
    return els.filter(e => !isNav(e)).map(e => e.href);
}
""".strip()

async def extract_links(page, base_url: str, base_domain: str) -> list[str]:
    try:
        hrefs = await page.eval_on_selector_all("a[href]", _NAV_JS)
    except Exception:
        return []

    seen, result = set(), []
    for href in hrefs:
        url = normalize_url(urljoin(base_url, href))
        if url in seen or not url.startswith("http"):
            continue
        seen.add(url)
        if (is_same_domain(url, base_domain)
                and is_html_url(url)
                and is_allowed_by_robots(url)):
            result.append(url)
    return result

# ─────────────────────────────────────────────────────────────────────────────
# PAGE VISIT
# ─────────────────────────────────────────────────────────────────────────────
async def visit_page(
    page, url: str, depth: int, base_domain: str, journal: dict, stats: dict
) -> list[str]:
    """Navigate to url, detect article, save if relevant. Returns child links."""
    log(f"[L{depth}] {url}")

    try:
        response = await page.goto(url, wait_until="networkidle", timeout=30000)

        if response and response.status in (403, 404, 410, 429, 503):
            log(f"  -> HTTP {response.status} — ignoré")
            journal[url] = {"status": "error", "code": response.status, "links": []}
            stats["errors"] += 1
            save_journal(journal)
            return []

        if await detect_antibot(page):
            await wait_for_human()
            await asyncio.sleep(2)
            await page.wait_for_load_state("networkidle", timeout=60000)

        html  = await page.content()
        links = await extract_links(page, url, base_domain)

        if is_news_page(html):
            year = extract_article_year(html, url)
            if not is_current_year(html, url):
                label = str(year) if year else "date inconnue"
                log(f"  -> article ignoré ({label}, hors année en cours)")
                journal[url] = {"status": "skipped_year", "year": year, "links": links}
                stats["skipped_year"] = stats.get("skipped_year", 0) + 1
            else:
                filename = generate_filename(url)
                Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
                (Path(OUTPUT_DIR) / filename).write_text(html, encoding="utf-8")
                label = str(year) if year else "année inconnue"
                log(f"  -> ARTICLE sauvegarde ({label}) : {filename}")
                journal[url] = {"status": "saved", "file": filename, "links": links}
                stats["saved"] += 1
        else:
            log(f"  -> page visitée (pas un article)")
            journal[url] = {"status": "visited", "links": links}
            stats["visited"] += 1

        save_journal(journal)
        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        return links

    except Exception as e:
        log(f"  -> Erreur : {e}")
        journal[url] = {"status": "error", "message": str(e), "links": []}
        stats["errors"] += 1
        save_journal(journal)
        return []

# ─────────────────────────────────────────────────────────────────────────────
# CRAWL SITE — BFS jusqu'à MAX_DEPTH
# ─────────────────────────────────────────────────────────────────────────────
async def crawl_site(page, seed_url: str, journal: dict, stats: dict):
    base_domain = get_domain(seed_url)
    log(f"\n{'─' * 60}")
    log(f"SITE : {seed_url}")
    log(f"{'─' * 60}")

    queue:   list[tuple[str, int]] = []
    queued:  set[str]              = set()

    def enqueue(url: str, depth: int):
        if url not in queued:
            queued.add(url)
            queue.append((url, depth))

    # Rebuild queue from journal on resume
    seed_data = journal.get(seed_url)
    if seed_data:
        log(f"  Reprise depuis le journal.")
        for l1_url in seed_data.get("links", []):
            enqueue(l1_url, 1)
            l1_data = journal.get(l1_url)
            if l1_data:
                for l2_url in l1_data.get("links", []):
                    enqueue(l2_url, 2)
    else:
