import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
from collections import defaultdict
import trafilatura

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INPUT_FILE = Path(r"C:/PYTHON/.entree/SitesSources/sites_actus_labos.txt")
OUTPUT_FILE = Path(r"C:/PYTHON/.data/Actualites_laboratoires.md")

LISTING_MIN_LINKS = 3             # Nb minimum de liens pour considérer une page comme liste
REQUEST_TIMEOUT = 30              # Timeout HTTP en secondes (Playwright)
NAVIGATION_PATHS = [
    "/about", "/contact", "/category", "/tag", "/author",
    "/search", "/login", "/register", "/privacy", "/terms",
    "/politique", "/mentions", "/legal",
]


# ---------------------------------------------------------------------------
# Chargement des URLs
# ---------------------------------------------------------------------------

def load_urls(filepath: str) -> list[str]:
    path = Path(filepath)
    if not path.exists():
        print(f"Erreur : fichier introuvable : {filepath}", file=sys.stderr)
        sys.exit(1)
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Regroupement par domaine
# ---------------------------------------------------------------------------

def get_domain(url: str) -> str:
    return urlparse(url).netloc


def group_urls_by_domain(urls: list[str]) -> dict[str, list[str]]:
    groups = defaultdict(list)
    for url in urls:
        groups[get_domain(url)].append(url)
    return groups


# ---------------------------------------------------------------------------
# Récupération du contenu HTML via Playwright
# ---------------------------------------------------------------------------

def fetch_html_with_page(playwright_page, url: str) -> str | None:
    try:
        playwright_page.goto(url, timeout=REQUEST_TIMEOUT * 1000, wait_until="domcontentloaded")
        return playwright_page.content()
    except Exception as e:
        print(f"Erreur lors de la récupération de {url} : {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Extraction des liens d'articles depuis une page de liste
# ---------------------------------------------------------------------------

def extract_article_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()

    # Recherche dans les balises sémantiques typiques des listes d'actualités
    for tag in soup.find_all(["article", "h2", "h3"]):
        for a in tag.find_all("a", href=True):
            url = urljoin(base_url, a["href"])
            if is_article_link(url, base_url):
                links.add(url)

    # Fallback : éléments avec classes contenant des mots-clés éditoriaux
    if not links:
        keywords = ["article", "news", "post", "story", "item"]
        for tag in soup.find_all(class_=lambda c: c and any(kw in " ".join(c).lower() for kw in keywords)):
            for a in tag.find_all("a", href=True):
                url = urljoin(base_url, a["href"])
                if is_article_link(url, base_url):
                    links.add(url)

    return list(links)


def is_article_link(url: str, base_url: str) -> bool:
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    if parsed.netloc != base_parsed.netloc:
        return False

    path = parsed.path.lower()
    if any(nav in path for nav in NAVIGATION_PATHS):
        return False

    # Chemin trop court pour être un article (ex: "/", "/fr")
    if len(parsed.path.strip("/")) < 3:
        return False

    return True


# ---------------------------------------------------------------------------
# Extraction du contenu d'un article
# ---------------------------------------------------------------------------

def extract_article(html: str, url: str) -> dict:
    result = trafilatura.bare_extraction(html, url=url, include_comments=False, include_tables=False)
    if result is None:
        return {"url": url, "title": "", "date": "", "authors": "", "description": "", "text": ""}
    return {
        "url": url,
        "title": getattr(result, "title", "") or "",
        "date": str(getattr(result, "date", "") or ""),
        "authors": getattr(result, "author", "") or "",
        "description": getattr(result, "description", "") or "",
        "text": getattr(result, "text", "") or "",
    }


# ---------------------------------------------------------------------------
# Mise en forme markdown
# ---------------------------------------------------------------------------

def format_article_to_markdown(article: dict) -> str:
    lines = []

    title = article.get("title") or "Sans titre"
    lines.append(f"# {title}")
    lines.append("")

    if article.get("date"):
        lines.append(f"**Date :** {article['date']}")
    if article.get("authors"):
        lines.append(f"**Auteur(s) :** {article['authors']}")
    lines.append(f"**Source :** {article['url']}")
    lines.append("")

    if article.get("description"):
        lines.append("## Résumé")
        lines.append("")
        lines.append(article["description"])
        lines.append("")

    if article.get("text"):
        lines.append("## Contenu")
        lines.append("")
        lines.append(article["text"])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Traitement d'une page (article direct ou page de liste)
# ---------------------------------------------------------------------------

def process_page(playwright_page, html: str, url: str) -> list[dict]:
    links = extract_article_links(html, url)

    if len(links) >= LISTING_MIN_LINKS:
        print(f"{len(links)} article(s) trouvé(s) sur la page de liste : {url}")
        articles = []
        for link in links:
            link_html = fetch_html_with_page(playwright_page, link)
            if link_html is None:
                continue
            article = extract_article(link_html, link)
            if article["text"] or article["title"]:
                articles.append(article)
        return articles
    else:
        article = extract_article(html, url)
        return [article] if (article["text"] or article["title"]) else []


# ---------------------------------------------------------------------------
# Traitement d'un domaine (un seul navigateur pour toutes ses pages)
# ---------------------------------------------------------------------------

def process_domain(domain: str, input_urls: list[str]) -> list[dict]:
    from playwright.sync_api import sync_playwright

    articles = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Première URL : navigation + pause pour résolution antibot éventuelle
        first_url = input_urls[0]
        html = fetch_html_with_page(page, first_url)
        if html is not None:
            input(f"\nDomaine : {domain}\nRésolvez le challenge antibot si nécessaire, puis appuyez sur Entrée...")
            html = page.content()  # contenu après résolution éventuelle
            articles.extend(process_page(page, html, first_url))

        # URLs suivantes du même domaine : pas de pause antibot
        for url in input_urls[1:]:
            html = fetch_html_with_page(page, url)
            if html is not None:
                articles.extend(process_page(page, html, url))

        browser.close()

    return articles


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    urls = load_urls(INPUT_FILE)
    domain_groups = group_urls_by_domain(urls)

    articles_md = []
    for domain, domain_urls in domain_groups.items():
        print(f"\nTraitement du domaine : {domain} ({len(domain_urls)} URL(s))")
        results = process_domain(domain, domain_urls)
        for article in results:
            articles_md.append(format_article_to_markdown(article))

    output = "\n\n---\n\n".join(articles_md)
    Path(OUTPUT_FILE).write_text(output, encoding="utf-8")
    print(f"\n{len(articles_md)} article(s) écrits dans {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
