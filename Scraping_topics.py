#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
topic_collector.py

Programme Python en ligne de commande qui :
- prend un sujet défini par TOPIC_GROUPS
- lit une liste de sources depuis un fichier texte
- cherche des résultats via DuckDuckGo avec Selenium
- filtre les pages HTML
- télécharge directement les PDF
- enregistre les fichiers retenus dans un dossier local

Décisions métier appliquées :
- HTML :
    * doit correspondre à TOPIC_GROUPS
    * doit faire au moins 100 mots
    * doit être daté de 2025 ou plus
    * doit être jugé intéressant par Ollama
- PDF :
    * téléchargement direct, sans contrôle de date ni de longueur
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, quote_plus, unquote, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager


# =============================================================================
# CONFIGURATION
# =============================================================================

TOPIC_GROUPS = [
    ["iran"],
    ["USA", "Israel"],
    ["crisis"],
]

SOURCES_FILE  = Path(r"C:/PYTHON/.entree/sources_iran.txt")
OUTPUT_DIR = Path(r"C:/PYTHON/.data/ResultatsScraping")

MAX_PER_SOURCE = 5
MAX_GLOBAL = 50

# Nombre de résultats bruts à demander avant filtrage local
SEARCH_BUFFER_PER_SOURCE = 20
SEARCH_BUFFER_GLOBAL = 120

RETRY_COUNT = 3
REQUEST_TIMEOUT = 25

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Ollama
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 90
MAX_OLLAMA_CHARS = 12000

# Filtre HTML
MIN_WORDS_HTML = 100
MIN_YEAR_HTML = 2025

# DuckDuckGo + Selenium
DUCKDUCKGO_BASE_URL = "https://duckduckgo.com/html/?q="
HEADLESS_BROWSER = False  # False recommandé : détection bot réduite
PAGE_LOAD_TIMEOUT = 35
RESULTS_WAIT_SECONDS = 2.0
BETWEEN_SEARCHES_SLEEP = 1.0

# Préfiltre simple d'URLs parasites
EXCLUDED_URL_PATTERNS = [
    "/tag/",
    "/tags/",
    "/category/",
    "/categories/",
    "/author/",
    "/authors/",
    "/search",
    "/login",
    "/signin",
    "/sign-in",
    "/account",
    "/register",
    "/signup",
    "/sign-up",
    "/wp-login",
]

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "ref_url",
}

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/pdf,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

STATS_TEMPLATE = {
    "sources_loaded": 0,
    "site_results_found": 0,
    "global_results_found": 0,
    "found_total": 0,
    "duplicates_removed": 0,
    "excluded_urls_removed": 0,
    "urls_unique": 0,
    "pdf_saved": 0,
    "html_saved": 0,
    "html_rejected_topic": 0,
    "html_rejected_short": 0,
    "html_rejected_old": 0,
    "html_rejected_ollama": 0,
    "html_rejected_no_date": 0,
    "other_skipped": 0,
    "download_errors": 0,
}


# =============================================================================
# TYPES
# =============================================================================

ResultItem = dict[str, Any]


# =============================================================================
# LOGS / UTILITAIRES
# =============================================================================

def log(message: str) -> None:
    """Affiche un message console simple."""
    print(message, flush=True)


def safe_strip(value: Optional[str]) -> str:
    """Retourne une chaîne nettoyée, même si value vaut None."""
    return value.strip() if value else ""


def quote_if_needed(term: str) -> str:
    """
    Met des guillemets autour d'un terme s'il contient plusieurs mots.
    """
    term = safe_strip(term)
    if not term:
        return term
    if " " in term:
        return f'"{term}"'
    return term


def now_str() -> str:
    """Retourne l'heure courante sous forme simple."""
    return datetime.now().strftime("%H:%M:%S")


# =============================================================================
# SOURCES
# =============================================================================

def normalize_source_entry(source: str) -> str:
    """
    Normalise une entrée source.

    Accepte :
    - exemple.com
    - https://example.com
    - http://www.example.com/news

    Retourne une URL propre.
    """
    source = safe_strip(source)
    if not source:
        return ""

    if not source.startswith(("http://", "https://")):
        source = "https://" + source

    parsed = urlparse(source)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    if netloc.startswith("www."):
        netloc = netloc[4:]

    if not netloc:
        return ""

    return urlunparse((scheme, netloc, path, "", "", ""))


def extract_domain(url: str) -> str:
    """Extrait le domaine utile pour site:domain."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def load_sources(file_path: str) -> list[str]:
    """
    Charge le fichier sources.txt et retourne une liste dédoublonnée.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier de sources introuvable : {file_path}")

    seen = set()
    sources: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = safe_strip(line)
            if not raw:
                continue
            normalized = normalize_source_entry(raw)
            if normalized and normalized not in seen:
                seen.add(normalized)
                sources.append(normalized)

    return sources


# =============================================================================
# REQUÊTES
# =============================================================================

def build_search_query_from_groups(topic_groups: list[list[str]]) -> str:
    """
    Construit une chaîne de recherche DuckDuckGo à partir de TOPIC_GROUPS.
    """
    chunks: list[str] = []

    for group in topic_groups:
        clean_terms = [quote_if_needed(term) for term in group if safe_strip(term)]
        if not clean_terms:
            continue

        if len(clean_terms) == 1:
            chunks.append(clean_terms[0])
        else:
            chunks.append("(" + " OR ".join(clean_terms) + ")")

    return " AND ".join(chunks)


def build_site_query(domain: str, topic_groups: list[list[str]]) -> str:
    """Construit une requête DuckDuckGo ciblée sur un domaine."""
    return f"site:{domain} {build_search_query_from_groups(topic_groups)}"


def build_global_query(topic_groups: list[list[str]]) -> str:
    """Construit une requête DuckDuckGo globale."""
    return build_search_query_from_groups(topic_groups)


def build_duckduckgo_url(query: str) -> str:
    """Construit l'URL DuckDuckGo HTML."""
    return DUCKDUCKGO_BASE_URL + quote_plus(query)


# =============================================================================
# PLAYWRIGHT / DUCKDUCKGO
# =============================================================================

def launch_browser() -> webdriver.Chrome:
    """
    Lance Selenium/Chrome avec options anti-détection et retourne le driver.
    """
    options = Options()
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=fr-FR")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if HEADLESS_BROWSER:
        options.add_argument("--headless=new")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    return driver


def close_browser(driver: webdriver.Chrome) -> None:
    """Ferme proprement le navigateur."""
    try:
        driver.quit()
    except Exception:
        pass


def clean_duckduckgo_result_url(url: str) -> str:
    """
    Nettoie certains liens issus de DuckDuckGo.

    DuckDuckGo HTML renvoie parfois des liens directs,
    parfois des redirections avec uddg.
    """
    url = safe_strip(url)
    if not url:
        return ""

    parsed = urlparse(url)
    query_map = dict(parse_qsl(parsed.query, keep_blank_values=True))

    # cas fréquent : redirection DuckDuckGo avec uddg
    if "uddg" in query_map:
        return unquote(query_map["uddg"])

    return url


def parse_search_results_from_page(
    html: str,
    query: str,
    source_type: str,
    site: Optional[str] = None,
) -> list[ResultItem]:
    """
    Extrait les résultats depuis la page HTML de DuckDuckGo.

    La structure de DuckDuckGo peut varier.
    On essaie donc plusieurs sélecteurs.
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[ResultItem] = []

    # Plusieurs formes de blocs possibles
    blocks = soup.select(".result, .results_links, .web-result, .result.results_links")

    seen_links: set[str] = set()

    for block in blocks:
        link_tag = (
            block.select_one("a.result__a")
            or block.select_one("a.result-link")
            or block.select_one("a.result__url")
            or block.select_one("a[href]")
        )

        if not link_tag:
            continue

        raw_href = safe_strip(link_tag.get("href"))
        if not raw_href:
            continue

        cleaned_href = clean_duckduckgo_result_url(raw_href)
        if not cleaned_href:
            continue

        title = safe_strip(link_tag.get_text(" ", strip=True))

        snippet_tag = (
            block.select_one(".result__snippet")
            or block.select_one(".snippet")
            or block.select_one(".result-snippet")
        )
        snippet = safe_strip(snippet_tag.get_text(" ", strip=True)) if snippet_tag else ""

        whole_text = block.get_text(" ", strip=True)
        search_year = extract_year_from_text(whole_text)

        # Éviter les répétitions exactes
        normalized_link = normalize_url(cleaned_href)
        if not normalized_link or normalized_link in seen_links:
            continue
        seen_links.add(normalized_link)

        results.append(
            {
                "url": cleaned_href,
                "title": title,
                "snippet": snippet,
                "search_year": search_year,
                "query": query,
                "source_type": source_type,
                "site": site,
            }
        )

    return results


def search_duckduckgo_with_browser(
    driver: webdriver.Chrome,
    query: str,
    max_results: int,
    source_type: str,
    site: Optional[str] = None,
    wait_for_user: bool = False,
) -> list[ResultItem]:
    """
    Lance une recherche DuckDuckGo via Selenium et retourne les résultats trouvés.

    Si wait_for_user=True, marque une pause après le chargement pour permettre
    de résoudre manuellement un puzzle anti-bot, puis reprend sur appui Entrée.
    """
    search_url = build_duckduckgo_url(query)
    log(f"[{now_str()}] [SEARCH] {query}")

    try:
        driver.get(search_url)
        time.sleep(RESULTS_WAIT_SECONDS)

        if wait_for_user:
            print("\n" + "=" * 70)
            print("PAUSE ANTI-BOT")
            print("Si un puzzle ou un captcha s'affiche dans le navigateur,")
            print("résolvez-le manuellement, puis appuyez sur Entrée ici.")
            print("=" * 70)
            input(">>> Appuyez sur Entrée pour continuer... ")
            print()

        page_html = driver.page_source

        log(f"[DEBUG] URL finale: {driver.current_url}")
        log(f"[DEBUG] Taille HTML: {len(page_html)}")
        log(f"[DEBUG] Début HTML: {page_html[:1000]}")

    except (TimeoutException, WebDriverException) as exc:
        raise RuntimeError(f"Erreur navigateur DuckDuckGo: {exc}") from exc

    parsed_results = parse_search_results_from_page(
        html=page_html,
        query=query,
        source_type=source_type,
        site=site,
    )

    log(f"[DEBUG] Résultats parsés: {len(parsed_results)}")

    return parsed_results[:max_results]


def collect_site_results(
    driver: webdriver.Chrome,
    sources: list[str],
    topic_groups: list[list[str]],
    max_per_source: int,
    search_buffer_per_source: int,
) -> list[ResultItem]:
    """
    Pour chaque source, lance une recherche DuckDuckGo ciblée.
    """
    all_results: list[ResultItem] = []

    for index, source in enumerate(sources, start=1):
        domain = extract_domain(source)
        query = build_site_query(domain, topic_groups)
        log(f"[{now_str()}] [SITE {index}/{len(sources)}] {domain}")

        try:
            raw_results = search_duckduckgo_with_browser(
                driver=driver,
                query=query,
                max_results=search_buffer_per_source,
                source_type="site",
                site=domain,
                wait_for_user=(index == 1),
            )
        except Exception as exc:
            log(f"[WARN] Recherche échouée pour {domain}: {exc}")
            time.sleep(BETWEEN_SEARCHES_SLEEP)
            continue

        # On garde les premiers résultats bruts. Le vrai filtrage se fera après.
        kept = raw_results[:max_per_source]
        all_results.extend(kept)

        time.sleep(BETWEEN_SEARCHES_SLEEP)

    return all_results


def collect_global_results(
    driver: webdriver.Chrome,
    topic_groups: list[list[str]],
    max_results: int,
    search_buffer_global: int,
    first_search: bool = False,
) -> list[ResultItem]:
    """
    Lance une recherche globale DuckDuckGo.
    """
    query = build_global_query(topic_groups)

    try:
        raw_results = search_duckduckgo_with_browser(
            driver=driver,
            query=query,
            max_results=search_buffer_global,
            source_type="global",
            site=None,
            wait_for_user=first_search,
        )
    except Exception as exc:
        log(f"[WARN] Recherche globale échouée: {exc}")
        return []

    return raw_results[:max_results]


# =============================================================================
# URLS : NETTOYAGE / DOUBLONS / EXCLUSION
# =============================================================================

def normalize_url(url: str) -> str:
    """
    Nettoie une URL pour comparaison.

    Actions :
    - retire certains paramètres de tracking
    - retire le fragment
    - harmonise le domaine
    - nettoie les slashs
    """
    url = safe_strip(url)
    if not url:
        return ""

    try:
        parsed = urlparse(url)
    except Exception:
        return ""

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    if not netloc:
        return ""

    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/":
        path = path.rstrip("/")

    filtered_params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_QUERY_PARAMS
    ]

    filtered_params.sort()
    clean_query = "&".join(
        f"{quote_plus(k)}={quote_plus(v)}" if v else quote_plus(k)
        for k, v in filtered_params
    )

    normalized = urlunparse((scheme, netloc, path, "", clean_query, ""))
    return normalized


def is_excluded_url(url: str) -> bool:
    """
    Rejette rapidement certaines URLs parasites.
    """
    lowered = url.lower()
    return any(pattern in lowered for pattern in EXCLUDED_URL_PATTERNS)


def deduplicate_results(results: list[ResultItem]) -> tuple[list[ResultItem], int, int]:
    """
    Supprime les doublons et certaines URLs simples à exclure.

    Retourne :
    - liste unique
    - nb doublons supprimés
    - nb URLs exclues
    """
    seen: set[str] = set()
    unique_results: list[ResultItem] = []
    duplicates_removed = 0
    excluded_removed = 0

    for item in results:
        raw_url = safe_strip(item.get("url"))
        if not raw_url:
            continue

        normalized = normalize_url(raw_url)
        if not normalized:
            continue

        if is_excluded_url(normalized):
            excluded_removed += 1
            continue

        if normalized in seen:
            duplicates_removed += 1
            continue

        seen.add(normalized)
        new_item = dict(item)
        new_item["url"] = normalized
        unique_results.append(new_item)

    return unique_results, duplicates_removed, excluded_removed


# =============================================================================
# RÉSEAU / TÉLÉCHARGEMENT
# =============================================================================

def fetch_url(url: str) -> Optional[tuple[int, dict[str, str], bytes]]:
    """
    Télécharge une URL avec requests.

    Retourne :
    - code HTTP
    - headers
    - contenu binaire
    """
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        return response.status_code, dict(response.headers), response.content
    except requests.RequestException:
        return None


def fetch_with_retries(url: str, retry_count: int) -> Optional[tuple[int, dict[str, str], bytes]]:
    """
    Réessaie plusieurs fois avant d'abandonner.
    """
    for attempt in range(1, retry_count + 1):
        result = fetch_url(url)
        if result is not None:
            return result

        log(f"[WARN] Téléchargement raté, nouvelle tentative {attempt}/{retry_count}: {url}")
        time.sleep(1.0)

    return None


def detect_content_type(url: str, headers: dict[str, str], content: bytes) -> str:
    """
    Détecte le type de contenu :
    - pdf
    - html
    - other
    """
    content_type = headers.get("Content-Type", "").lower()
    lowered_url = url.lower()
    prefix = content[:800].lower()

    if "application/pdf" in content_type:
        return "pdf"
    if lowered_url.endswith(".pdf"):
        return "pdf"
    if content.startswith(b"%PDF"):
        return "pdf"

    if "text/html" in content_type:
        return "html"
    if b"<html" in prefix or b"<!doctype html" in prefix:
        return "html"

    return "other"


# =============================================================================
# HTML : EXTRACTION / TEXTE / DATES
# =============================================================================

def decode_html(content: bytes, headers: dict[str, str]) -> str:
    """
    Décode des octets HTML en texte.
    """
    content_type = headers.get("Content-Type", "")
    charset_match = re.search(r"charset=([\w\-]+)", content_type, flags=re.IGNORECASE)

    if charset_match:
        encoding = charset_match.group(1)
        try:
            return content.decode(encoding, errors="replace")
        except LookupError:
            pass
        except Exception:
            pass

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding, errors="replace")
        except Exception:
            continue

    return content.decode(errors="replace")


def extract_basic_html_text(html: str) -> str:
    """
    Extrait un texte brut simple du HTML.

    Ce n'est pas une extraction éditoriale parfaite.
    Le but est :
    - présence des groupes de mots
    - longueur
    - date
    - envoi à Ollama
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "iframe", "canvas", "form"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_text(text: str) -> str:
    """
    Passe en minuscules et simplifie les espaces.
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def matches_topic_groups(text: str, topic_groups: list[list[str]]) -> bool:
    """
    Retourne True si au moins un terme de chaque groupe est trouvé.
    """
    normalized_text = normalize_text(text)

    for group in topic_groups:
        group_ok = False

        for term in group:
            candidate = normalize_text(term)
            if candidate and candidate in normalized_text:
                group_ok = True
                break

        if not group_ok:
            return False

    return True


def count_words(text: str) -> int:
    """
    Compte les mots de manière simple.
    """
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def extract_year_from_text(text: str) -> Optional[int]:
    """
    Cherche une année plausible dans un texte.
    Retourne l'année la plus récente trouvée.
    """
    years = re.findall(r"\b(20\d{2})\b", text)
    if not years:
        return None

    parsed_years = [int(y) for y in years if 2000 <= int(y) <= 2099]
    if not parsed_years:
        return None

    return max(parsed_years)


def extract_year_from_search_result(result: ResultItem) -> Optional[int]:
    """
    Extrait l'année détectée dans le résultat de recherche.
    """
    year = result.get("search_year")
    if isinstance(year, int):
        return year
    return None


def extract_year_from_html_meta(soup: BeautifulSoup) -> Optional[int]:
    """
    Cherche l'année dans les métadonnées HTML courantes.
    """
    meta_selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "publishdate"}),
        ("meta", {"name": "date"}),
        ("meta", {"itemprop": "datePublished"}),
        ("meta", {"property": "og:updated_time"}),
        ("meta", {"name": "lastmod"}),
    ]

    for tag_name, attrs in meta_selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if not tag:
            continue

        content = safe_strip(tag.get("content") or tag.get("value") or "")
        year = extract_year_from_text(content)
        if year:
            return year

    return None


def extract_year_from_html(html: str, text: str) -> Optional[int]:
    """
    Cherche une année dans :
    - métadonnées HTML
    - balises time
    - JSON-LD
    - texte visible
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) métadonnées
    year = extract_year_from_html_meta(soup)
    if year:
        return year

    # 2) balises <time>
    for time_tag in soup.find_all("time"):
        combined = " ".join(
            part for part in [
                safe_strip(time_tag.get("datetime")),
                safe_strip(time_tag.get_text(" ", strip=True)),
            ] if part
        )
        year = extract_year_from_text(combined)
        if year:
            return year

    # 3) JSON-LD
    json_ld_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    for tag in json_ld_tags:
        raw = safe_strip(tag.string or tag.get_text())
        if not raw:
            continue
        year = extract_year_from_text(raw)
        if year:
            return year

    # 4) texte visible
    return extract_year_from_text(text)


def is_recent_enough(year: Optional[int], min_year: int) -> bool:
    """
    Retourne True si l'année est suffisante.
    """
    if year is None:
        return False
    return year >= min_year


# =============================================================================
# OLLAMA
# =============================================================================

def build_ollama_prompt(text: str) -> str:
    """
    Construit le prompt envoyé à Ollama.
    """
    excerpt = text[:MAX_OLLAMA_CHARS]

    return (
        "Tu évalues si un document web a un intérêt informationnel.\n\n"
        "Réponds uniquement en JSON valide.\n"
        'Format exact attendu : {"interessant": true} ou {"interessant": false}\n\n'
        "Règles :\n"
        "- false si le contenu est marketing, commercial, promotionnel ou publicitaire\n"
        "- false si le contenu est très pauvre, creux ou sans vraie valeur informative\n"
        "- true si le contenu est informatif, éditorial, analytique, scientifique, "
        "institutionnel ou journalistique\n\n"
        "Texte à évaluer :\n"
        f"{excerpt}"
    )


def parse_ollama_json(response_text: str) -> Optional[bool]:
    """
    Essaie de récupérer le booléen 'interessant' dans la réponse d'Ollama.
    """
    response_text = safe_strip(response_text)
    if not response_text:
        return None

    # Cas direct
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, dict) and "interessant" in parsed:
            return bool(parsed["interessant"])
    except json.JSONDecodeError:
        pass

    # Cas où le modèle ajoute du texte autour
    match = re.search(r"\{.*?\}", response_text, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "interessant" in parsed:
                return bool(parsed["interessant"])
        except json.JSONDecodeError:
            return None

    return None


def ask_ollama_for_html(text: str) -> bool:
    """
    Envoie le texte à Ollama.
    Retourne False en cas d'erreur ou de réponse illisible.
    """
    prompt = build_ollama_prompt(text)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        log(f"[WARN] Ollama indisponible ou réponse invalide: {exc}")
        return False

    raw_response = safe_strip(data.get("response", ""))
    parsed = parse_ollama_json(raw_response)
    if parsed is None:
        return False
    return parsed


# =============================================================================
# SAUVEGARDE
# =============================================================================

def sanitize_filename(name: str) -> str:
    """
    Nettoie un nom pour en faire un nom de fichier valide.
    """
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("._")
    return name or "document"


def make_filename_from_url(url: str, content_type: str) -> str:
    """
    Fabrique un nom de fichier basé sur l'URL.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.strip("/")

    if not path:
        path = "root"

    parts = [domain, path]
    if parsed.query:
        parts.append(parsed.query)

    base = sanitize_filename("_".join(parts))

    ext = ".pdf" if content_type == "pdf" else ".html"
    return base + ext


def ensure_unique_path(path: Path) -> Path:
    """
    Si le fichier existe déjà, ajoute _2, _3, etc.
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def inject_base_tag(content: bytes, url: str) -> bytes:
    """
    Injecte <base href="url"> dans le <head> du HTML.

    Cela permet au navigateur de résoudre correctement toutes les URLs
    relatives (CSS, images, polices, scripts) vers le site d'origine,
    même quand le fichier est ouvert en local.
    """
    try:
        soup = BeautifulSoup(content, "lxml")
        if not soup.find("base"):
            base_tag = soup.new_tag("base", href=url)
            head = soup.find("head")
            if head:
                head.insert(0, base_tag)
            else:
                # Pas de <head> : on l'insère en tête du document
                soup.insert(0, base_tag)
        return str(soup).encode("utf-8")
    except Exception:
        return content


def save_binary_file(path: Path, content: bytes) -> None:
    """
    Sauvegarde un fichier binaire.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(content)


def prepare_output_dir(path: str) -> Path:
    """
    Vide le dossier de sortie puis le recrée.
    """
    output = Path(path)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


# =============================================================================
# TRAITEMENT DES DOCUMENTS
# =============================================================================

def process_pdf(
    result: ResultItem,
    content: bytes,
    output_dir: Path,
    stats: dict[str, int],
) -> None:
    """
    Sauvegarde directement un PDF.
    """
    filename = make_filename_from_url(result["url"], "pdf")
    save_path = ensure_unique_path(output_dir / filename)
    save_binary_file(save_path, content)
    stats["pdf_saved"] += 1
    log(f"[SAVE PDF] {save_path.name}")


def process_html(
    result: ResultItem,
    headers: dict[str, str],
    content: bytes,
    output_dir: Path,
    stats: dict[str, int],
) -> None:
    """
    Traite et filtre un HTML selon les règles métier.
    """
    html = decode_html(content, headers)
    text = extract_basic_html_text(html)

    if not matches_topic_groups(text, TOPIC_GROUPS):
        stats["html_rejected_topic"] += 1
        return

    words = count_words(text)
    if words < MIN_WORDS_HTML:
        stats["html_rejected_short"] += 1
        return

    year = extract_year_from_search_result(result)
    if year is None:
        year = extract_year_from_html(html, text)

    if year is None:
        stats["html_rejected_no_date"] += 1
        return

    if not is_recent_enough(year, MIN_YEAR_HTML):
        stats["html_rejected_old"] += 1
        return

    if not ask_ollama_for_html(text):
        stats["html_rejected_ollama"] += 1
        return

    filename = make_filename_from_url(result["url"], "html")
    save_path = ensure_unique_path(output_dir / filename)
    save_binary_file(save_path, inject_base_tag(content, result["url"]))
    stats["html_saved"] += 1
    log(f"[SAVE HTML] {save_path.name}")


# =============================================================================
# RÉSUMÉ
# =============================================================================

def print_summary(stats: dict[str, int]) -> None:
    """
    Affiche un résumé final.
    """
    print("\n=== Résumé ===")
    print(f"Sources chargées : {stats['sources_loaded']}")
    print(f"Résultats trouvés sur sources : {stats['site_results_found']}")
    print(f"Résultats trouvés en global : {stats['global_results_found']}")
    print(f"Résultats trouvés au total : {stats['found_total']}")
    print(f"Doublons supprimés : {stats['duplicates_removed']}")
    print(f"URLs exclues par règle simple : {stats['excluded_urls_removed']}")
    print(f"URLs uniques : {stats['urls_unique']}")
    print()
    print(f"PDF enregistrés : {stats['pdf_saved']}")
    print(f"HTML enregistrés : {stats['html_saved']}")
    print()
    print(f"HTML rejetés (hors sujet) : {stats['html_rejected_topic']}")
    print(f"HTML rejetés (trop courts) : {stats['html_rejected_short']}")
    print(f"HTML rejetés (trop anciens) : {stats['html_rejected_old']}")
    print(f"HTML rejetés (pas de date) : {stats['html_rejected_no_date']}")
    print(f"HTML rejetés (Ollama) : {stats['html_rejected_ollama']}")
    print()
    print(f"Autres types ignorés : {stats['other_skipped']}")
    print(f"Erreurs de téléchargement : {stats['download_errors']}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Point d'entrée principal.
    """
    stats = dict(STATS_TEMPLATE)

    log("=== Démarrage du collecteur ===")

    # 1. Charger les sources
    try:
        sources = load_sources(SOURCES_FILE)
    except Exception as exc:
        log(f"[ERREUR] Impossible de lire {SOURCES_FILE}: {exc}")
        sys.exit(1)

    stats["sources_loaded"] = len(sources)
    log(f"[INFO] Sources chargées : {len(sources)}")

    # 2. Préparer le dossier de sortie
    try:
        output_dir = prepare_output_dir(OUTPUT_DIR)
    except Exception as exc:
        log(f"[ERREUR] Impossible de préparer le dossier de sortie: {exc}")
        sys.exit(1)

    log(f"[INFO] Dossier de sortie prêt : {output_dir.resolve()}")

    # 3. Collecter les résultats DuckDuckGo avec Selenium
    driver = None

    site_results: list[ResultItem] = []
    global_results: list[ResultItem] = []

    try:
        driver = launch_browser()

        site_results = collect_site_results(
            driver=driver,
            sources=sources,
            topic_groups=TOPIC_GROUPS,
            max_per_source=MAX_PER_SOURCE,
            search_buffer_per_source=SEARCH_BUFFER_PER_SOURCE,
        )
        stats["site_results_found"] = len(site_results)

        global_results = collect_global_results(
            driver=driver,
            topic_groups=TOPIC_GROUPS,
            max_results=MAX_GLOBAL,
            search_buffer_global=SEARCH_BUFFER_GLOBAL,
            first_search=(len(sources) == 0),
        )
        stats["global_results_found"] = len(global_results)

    except Exception as exc:
        log(f"[WARN] Problème pendant les recherches DuckDuckGo: {exc}")

    finally:
        if driver is not None:
            close_browser(driver)

    # 4. Fusion
    all_results = site_results + global_results
    stats["found_total"] = len(all_results)
    log(f"[INFO] Résultats bruts collectés : {len(all_results)}")

    # 5. Déduplication + exclusion
    unique_results, duplicates_removed, excluded_removed = deduplicate_results(all_results)
    stats["duplicates_removed"] = duplicates_removed
    stats["excluded_urls_removed"] = excluded_removed
    stats["urls_unique"] = len(unique_results)

    log(f"[INFO] URLs uniques à traiter : {len(unique_results)}")

    # 6. Télécharger et traiter
    for index, result in enumerate(unique_results, start=1):
        url = result["url"]
        log(f"[{index}/{len(unique_results)}] {url}")

        fetched = fetch_with_retries(url, RETRY_COUNT)
        if fetched is None:
            stats["download_errors"] += 1
            continue

        status_code, headers, content = fetched
        if status_code >= 400:
            stats["download_errors"] += 1
            continue

        content_type = detect_content_type(url, headers, content)

        if content_type == "pdf":
            try:
                process_pdf(result, content, output_dir, stats)
            except Exception as exc:
                stats["download_errors"] += 1
                log(f"[WARN] Erreur sauvegarde PDF : {exc}")

        elif content_type == "html":
            try:
                process_html(result, headers, content, output_dir, stats)
            except Exception as exc:
                stats["download_errors"] += 1
                log(f"[WARN] Erreur traitement HTML : {exc}")

        else:
            stats["other_skipped"] += 1

    # 7. Résumé final
    print_summary(stats)


if __name__ == "__main__":
    main()